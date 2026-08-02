import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.market_overview_repository import MarketOverviewRepository
from app.repositories.market_repository import MarketRepository
from app.schemas.market import (
    BoardItemView,
    BoardSectionView,
    MarketIndexConfigCreateRequest,
    MarketIndexConfigUpdateRequest,
    MarketIndexConfigView,
    MarketKlineView,
    MarketOverviewMarketView,
    MarketOverviewView,
    MarketRefreshResultView,
    MarketSparklineRequest,
    NewsSentimentView,
    NewsSignalItemView,
    OverviewIndexQuoteView,
    PriceSnapshotView,
    QuantSentimentInputsView,
    QuantSentimentView,
    QuoteDetailView,
    QuoteSummaryView,
    SparklineSeriesView,
)
from app.services.board_provider import BoardFetchResult, get_cached_industry_boards
from app.services.event_bus import get_event_bus
from app.services.market_chart_service import MarketChartService
from app.services.market_hours import is_overview_market_open
from app.services.market_overview_service import (
    MARKET_DISPLAY_NAMES,
    OVERVIEW_MARKETS,
    VIX_SYMBOL,
    IndexQuoteRow,
    MarketOverviewService,
)
from app.services.market_sentiment_service import (
    BoardStats,
    SentimentIndexQuote,
    aggregate_all_markets,
    compute_market_sentiment,
)
from app.services.quote_service import QuoteService

router = APIRouter()
logger = logging.getLogger(__name__)

# Yahoo 在线搜索的**整体**墙钟上限。httpx 的 timeout=0.5 只覆盖单个 IO 阶段，
# DNS 解析 / TLS 建连在被墙的网络下可以额外挂住好几秒，所以必须再套一层
# 「不管卡在哪一步，超过这个时间就放弃、立刻降级到本地结果」的硬上限。
_YAHOO_SEARCH_BUDGET_SECONDS = 1.0

_search_pool: ThreadPoolExecutor | None = None
_search_pool_lock = threading.Lock()


def _get_search_pool() -> ThreadPoolExecutor:
    """懒加载的共享线程池：不在请求线程里直接发起外部请求。"""
    global _search_pool
    with _search_pool_lock:
        if _search_pool is None:
            _search_pool = ThreadPoolExecutor(
                max_workers=max(1, int(getattr(get_settings(), "market_chart_max_workers", 8))),
                thread_name_prefix="market-search",
            )
        return _search_pool


def _fetch_yahoo_search(query: str) -> list[dict]:
    """在工作线程里调用 Yahoo 搜索，返回原始 quotes 列表；任何失败都返回空列表。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = httpx.get(
        f"https://query1.finance.yahoo.com/v1/finance/search?q={query}",
        headers=headers,
        timeout=0.5,
    )
    if res.status_code != 200:
        return []
    data = res.json()
    quotes = data.get("quotes", [])
    return quotes if isinstance(quotes, list) else []


def get_quote_service() -> QuoteService:
    return QuoteService()


def get_market_chart_service() -> MarketChartService:
    return MarketChartService()


@router.get("/snapshots", response_model=list[PriceSnapshotView])
def list_market_snapshots(session: Session = Depends(get_db_session)) -> list[PriceSnapshotView]:
    repository = MarketRepository(session)
    snapshots = repository.list_latest()
    response: list[PriceSnapshotView] = []
    for snapshot in snapshots:
        is_abnormal = abs(snapshot.change_percent or 0.0) >= 3
        response.append(
            PriceSnapshotView(
                symbol=snapshot.symbol,
                market=snapshot.market,
                display_name=None,
                provider_symbol=snapshot.provider_symbol,
                price=snapshot.price,
                change_amount=snapshot.change_amount,
                change_percent=snapshot.change_percent,
                open_price=snapshot.open_price,
                previous_close=snapshot.previous_close,
                day_high=snapshot.day_high,
                day_low=snapshot.day_low,
                volume=snapshot.volume,
                status=snapshot.quote_status or "ok",
                source=snapshot.provider_name,
                message=snapshot.status_message,
                is_abnormal=is_abnormal,
                abnormal_reason="price_move" if is_abnormal else None,
                fetched_at=snapshot.fetched_at,
            )
        )
    return response


@router.get("/watchlist", response_model=list[QuoteSummaryView])
def list_watchlist_quotes(session: Session = Depends(get_db_session)) -> list[QuoteSummaryView]:
    service = get_quote_service()
    quotes = service.get_cached_watchlist_quotes(session)
    return [QuoteSummaryView.model_validate(item) for item in quotes]


@router.get("/symbols/{symbol}", response_model=QuoteDetailView)
def get_symbol_quote(symbol: str, session: Session = Depends(get_db_session)) -> QuoteDetailView:
    service = get_quote_service()
    return QuoteDetailView.model_validate(service.get_cached_symbol_quote(symbol, session))


@router.get("/symbols/{symbol}/kline", response_model=MarketKlineView)
def get_symbol_kline(
    symbol: str,
    interval: str = "1d",
    range: str = "6mo",
    session: Session = Depends(get_db_session),
) -> MarketKlineView:
    service = get_market_chart_service()
    return MarketKlineView.model_validate(service.get_kline(symbol, interval, range, session))


@router.post("/sparklines", response_model=dict[str, SparklineSeriesView])
def get_watchlist_sparklines(
    payload: MarketSparklineRequest,
    session: Session = Depends(get_db_session),
) -> dict[str, SparklineSeriesView]:
    if len(payload.symbols) > 30:
        raise HTTPException(status_code=400, detail="too many symbols")
    service = get_market_chart_service()
    sparkline_map = service.get_sparklines(payload.symbols, session)
    return {symbol: SparklineSeriesView.model_validate(data) for symbol, data in sparkline_map.items()}


@router.post("/refresh", response_model=MarketRefreshResultView)
def refresh_market_quotes(session: Session = Depends(get_db_session)) -> MarketRefreshResultView:
    service = get_quote_service()
    # 手动刷新是用户"我现在就要最新价"的明确意图，必须绕过读路径的 180s 缓存 TTL；
    # 连点保护由 QuoteService.force_min_interval（默认 5s）兜住。
    quotes = service.refresh_watchlist_quotes(session, force=True)
    get_event_bus().publish(
        "market.watchlist_refreshed",
        {
            "symbols": [str(q.get("symbol")) for q in quotes if q.get("symbol")],
            "quotes": quotes,
        },
    )
    return MarketRefreshResultView(
        quotes_count=len(quotes),
        symbols=[str(q.get("symbol")) for q in quotes if q.get("symbol")],
        triggered_at=datetime.now(UTC),
    )


@router.get("/search")
def search_market_symbols(q: str, session: Session = Depends(get_db_session)):
    query = q.strip()
    if not query:
        return []

    q_lower = query.lower()
    results: list[dict[str, str]] = []
    seen_symbols: set[str] = set()

    # 1. 优先在内置预置候选库及全量 A 股内存数据库中极速搜索
    from app.services.a_share_search_service import search_a_shares
    from app.services.quote_provider import normalize_symbol
    from app.services.watchlist_candidates import list_watchlist_candidates

    for candidate in list_watchlist_candidates():
        symbol = str(candidate["symbol"])
        display_name = str(candidate.get("display_name", symbol))
        market = str(candidate.get("market", "us"))
        aliases = [str(a).lower() for a in candidate.get("aliases", [])]

        if (
            q_lower in symbol.lower()
            or q_lower in display_name.lower()
            or any(q_lower in alias for alias in aliases)
        ):
            results.append({
                "symbol": symbol,
                "display_name": display_name,
                "market": market,
                "type": "EQUITY",
            })
            seen_symbols.add(symbol)

    # 1.5 极速内存检索全量 6000+ A股 (含拼音/代码/中文全称)
    a_share_matches = search_a_shares(query, limit=30)
    for stock in a_share_matches:
        symbol = stock["symbol"]
        if symbol not in seen_symbols:
            results.append({
                "symbol": symbol,
                "display_name": stock["display_name"],
                "market": "cn",
                "type": "EQUITY",
            })
            seen_symbols.add(symbol)

    # 性能核心优化:
    # 1. 如果本地全量 A 股或预置候选库已经找到了结果，或者搜索包含中文，直接 0.5ms 内秒级返回！
    # 2. 避免无谓挂起等待由于国内网络被墙导致的 2 秒 Yahoo 网络超时卡顿。
    is_chinese = any("\u4e00" <= char <= "\u9fff" for char in query)
    if len(results) >= 5 or is_chinese:
        return results

    # 2. 仅在本地命中少且为英文/数字代码时，才尝试极速探查 Yahoo。
    #    请求丢到共享线程池里跑，并对**整体**耗时设 _YAHOO_SEARCH_BUDGET_SECONDS
    #    的硬上限：超时/失败都立刻放弃并降级到下面的本地结果，绝不拖住请求线程
    #    （请求线程还攥着一条 SQLite 连接）。
    quotes: list[dict] = []
    future = _get_search_pool().submit(_fetch_yahoo_search, query)
    try:
        quotes = future.result(timeout=_YAHOO_SEARCH_BUDGET_SECONDS)
    except Exception as exc:
        # 超时 / 连接失败 / 解析失败：一律快速降级到本地结果。
        future.cancel()
        logger.warning("yahoo symbol search degraded to local results (%s): %s", query, exc)
        quotes = []

    for item in quotes:
        if not isinstance(item, dict):
            continue
        raw_symbol = item.get("symbol")
        if not raw_symbol:
            continue
        shortname = item.get("shortname") or item.get("longname") or raw_symbol
        quote_type = item.get("quoteType", "EQUITY")

        # 规范化大A股票代码: .SS -> .SH
        market = "us"
        normalized_sym = raw_symbol
        exchange = item.get("exchange")
        if raw_symbol.endswith(".HK") or exchange == "HKG":
            market = "hk"
        elif raw_symbol.endswith(".SS") or raw_symbol.endswith(".SH") or raw_symbol.endswith(".SZ") or exchange in {"SHH", "SHE"}:
            market = "cn"
            try:
                normalized_sym = normalize_symbol(raw_symbol, "cn").symbol
            except ValueError:
                normalized_sym = raw_symbol.replace(".SS", ".SH")

        if normalized_sym not in seen_symbols:
            results.append({
                "symbol": normalized_sym,
                "display_name": shortname,
                "market": market,
                "type": quote_type,
            })
            seen_symbols.add(normalized_sym)

    # 3. Local fallback: search in price_snapshot。
    #    这条 LIKE '%q%' 是 price_snapshot 全表扫，结果已经够多时没必要再付这个代价。
    if len(results) < 10:
        from app.models.price_snapshot import PriceSnapshot

        stmt = (
            select(PriceSnapshot)
            .where(
                PriceSnapshot.symbol.like(f"%{query}%") |
                PriceSnapshot.provider_symbol.like(f"%{query}%")
            )
            .limit(10)
        )
        for snapshot in session.scalars(stmt):
            if snapshot.symbol not in seen_symbols:
                results.append({
                    "symbol": snapshot.symbol,
                    "display_name": snapshot.symbol,
                    "market": snapshot.market,
                    "type": "EQUITY",
                })
                seen_symbols.add(snapshot.symbol)

    # 4. 兜底逻辑：如果用户输入的是符合规范的大A股票代码(如 6 位数字 600900 / 000858，或 SH600900 / 600900.SH)，自动生成标准化 A 股候选
    try:
        norm = normalize_symbol(query, "cn")
        if norm.symbol not in seen_symbols:
            results.append({
                "symbol": norm.symbol,
                "display_name": f"{norm.symbol} (A股)",
                "market": "cn",
                "type": "EQUITY",
            })
            seen_symbols.add(norm.symbol)
    except ValueError:
        pass

    return results




# ---------------------------------------------------------------------------
# 市场总览（Market Overview）：/overview 聚合端点 + 指数配置 CRUD
# 契约见 docs/superpowers/specs/2026-08-02-market-overview-design.md 九节。
# ---------------------------------------------------------------------------

# 指数配置允许的市场与 kind（单用户全局配置，无 hk；hk 指数不在本期覆盖范围）。
_OVERVIEW_CONFIG_MARKETS = frozenset(OVERVIEW_MARKETS)
_OVERVIEW_CONFIG_KINDS = frozenset({"index", "etf"})


def get_market_overview_service() -> MarketOverviewService:
    return MarketOverviewService()


def _build_board_section(
    market: str,
    etf_rows: list[IndexQuoteRow],
    board_result: BoardFetchResult,
) -> BoardSectionView:
    """板块区三分支：cn=东财行业榜 / us,eu=预置 ETF（配置表 kind=etf 行）/ kr,jp=none。"""
    if market == "cn":
        return BoardSectionView(
            status=board_result.status,
            stale=board_result.stale,
            source="eastmoney",
            items=[
                BoardItemView(
                    code=item.code,
                    name=item.name,
                    price=item.price,
                    change_percent=item.change_percent,
                    advance_count=item.advance_count,
                    decline_count=item.decline_count,
                    flat_count=item.flat_count,
                    net_inflow=item.net_inflow,
                    fetched_at=item.fetched_at,
                )
                for item in board_result.items
            ],
            message=board_result.message,
        )
    if market in ("us", "eu"):
        return BoardSectionView(
            status="ok",
            stale=False,
            source="preset_etf",
            items=[
                BoardItemView(
                    code=row.symbol,
                    name=row.display_name,
                    price=row.price,
                    change_percent=row.change_percent,
                    fetched_at=row.fetched_at,
                )
                for row in etf_rows
            ],
        )
    return BoardSectionView(status="none", stale=False, source="none", items=[])


@router.get("/overview", response_model=MarketOverviewView)
def get_market_overview(session: Session = Depends(get_db_session)) -> MarketOverviewView:
    """五市场骨架聚合：指数快照 + 量化情绪 + 板块区 + 新闻情绪。

    读路径只查库 + 读进程内缓存，不阻塞等待外网（板块缓存为空的零延迟保底
    抓取带 5s 超时除外）。配置表为空时由 service 回落内置默认清单。
    """
    settings = get_settings()
    service = get_market_overview_service()
    quote_rows = service.list_index_quotes(session)
    news_map = aggregate_all_markets(
        session,
        lookback_hours=float(settings.market_overview_news_lookback_hours),
    )
    # cn 的板块榜与涨跌家数（量化情绪输入）共用这一份缓存结果。
    board_result = get_cached_industry_boards(
        ttl_seconds=float(settings.market_board_cache_ttl_seconds)
    )

    markets: list[MarketOverviewMarketView] = []
    for market in OVERVIEW_MARKETS:
        rows = [row for row in quote_rows if row.market == market]
        # ^VIX 不在指数行展示，只提供量化情绪的 VIX 输入（设计文档十三.1 定案）。
        index_rows = [row for row in rows if row.kind == "index" and row.symbol != VIX_SYMBOL]
        etf_rows = [row for row in rows if row.kind == "etf"]
        vix_row = next((row for row in rows if row.symbol == VIX_SYMBOL), None)

        board_stats = None
        if market == "cn" and board_result.status == "ok" and board_result.items:
            board_stats = BoardStats(
                advance_count=sum(item.advance_count or 0 for item in board_result.items),
                decline_count=sum(item.decline_count or 0 for item in board_result.items),
                flat_count=sum(item.flat_count or 0 for item in board_result.items),
            )
        quant = compute_market_sentiment(
            [SentimentIndexQuote(change_percent=row.change_percent) for row in index_rows],
            vix=vix_row.price if vix_row is not None and vix_row.status == "ok" else None,
            board_stats=board_stats,
        )

        news = news_map[market]
        markets.append(
            MarketOverviewMarketView(
                market=market,
                display_name=MARKET_DISPLAY_NAMES[market],
                is_open=is_overview_market_open(market),
                indices=[
                    OverviewIndexQuoteView(
                        symbol=row.symbol,
                        display_name=row.display_name,
                        kind=row.kind,
                        price=row.price,
                        change_percent=row.change_percent,
                        previous_close=row.previous_close,
                        status=row.status,
                        fetched_at=row.fetched_at,
                    )
                    for row in index_rows
                ],
                quant_sentiment=QuantSentimentView(
                    score=quant.score,
                    label=quant.label,
                    inputs=QuantSentimentInputsView(**quant.inputs),
                ),
                boards=_build_board_section(market, etf_rows, board_result),
                news_sentiment=NewsSentimentView(
                    status=news.status,
                    score=news.score,
                    sample_count=news.sample_count,
                    top_signals=[
                        NewsSignalItemView(
                            news_id=signal.news_id,
                            title=signal.title,
                            summary=signal.summary,
                            signal_confidence=signal.signal_confidence,
                            source_name=signal.source_name,
                            published_at=signal.published_at,
                            canonical_url=signal.canonical_url,
                        )
                        for signal in news.top_signals
                    ],
                ),
            )
        )
    return MarketOverviewView(generated_at=datetime.now(UTC), markets=markets)


@router.get("/index-config", response_model=list[MarketIndexConfigView])
def list_market_index_config(session: Session = Depends(get_db_session)) -> list:
    """全部指数配置（含 disabled），按 (market, sort_order) 排序。"""
    return MarketOverviewRepository(session).list_all()


@router.post("/index-config", response_model=MarketIndexConfigView, status_code=201)
def create_market_index_config(
    payload: MarketIndexConfigCreateRequest,
    session: Session = Depends(get_db_session),
):
    market = payload.market.strip().lower()
    if market not in _OVERVIEW_CONFIG_MARKETS:
        raise HTTPException(status_code=400, detail=f"unsupported market: {payload.market!r}")
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol must not be blank")
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name must not be blank")
    if payload.kind not in _OVERVIEW_CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"unsupported kind: {payload.kind!r}")

    try:
        return MarketOverviewRepository(session).create(
            symbol=symbol,
            market=market,
            display_name=display_name,
            kind=payload.kind,
            sort_order=payload.sort_order,
            enabled=payload.enabled,
        )
    except IntegrityError:
        # 同 (symbol, market) 唯一冲突；回滚交给 get_db_session 的异常分支。
        raise HTTPException(
            status_code=409,
            detail=f"index config already exists for ({symbol}, {market})",
        ) from None


@router.patch("/index-config/{config_id}", response_model=MarketIndexConfigView)
def update_market_index_config(
    config_id: int,
    payload: MarketIndexConfigUpdateRequest,
    session: Session = Depends(get_db_session),
):
    # symbol/market 不在请求模型里（extra="forbid"），到这里只剩白名单字段。
    updates = payload.model_dump(exclude_unset=True)
    if "kind" in updates and updates["kind"] not in _OVERVIEW_CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"unsupported kind: {updates['kind']!r}")
    if "display_name" in updates and not updates["display_name"].strip():
        raise HTTPException(status_code=400, detail="display_name must not be blank")

    item = MarketOverviewRepository(session).update(config_id, updates)
    if item is None:
        raise HTTPException(status_code=404, detail="index config not found")
    return item


@router.delete("/index-config/{config_id}", status_code=204)
def delete_market_index_config(
    config_id: int,
    session: Session = Depends(get_db_session),
) -> None:
    """物理删除（单用户本地应用，不做回收站）。"""
    if not MarketOverviewRepository(session).delete(config_id):
        raise HTTPException(status_code=404, detail="index config not found")
