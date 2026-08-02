import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.market_repository import MarketRepository
from app.schemas.market import (
    MarketKlineView,
    MarketRefreshResultView,
    MarketSparklineRequest,
    PriceSnapshotView,
    QuoteDetailView,
    QuoteSummaryView,
    SparklineSeriesView,
)
from app.services.event_bus import get_event_bus
from app.services.market_chart_service import MarketChartService
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
        logger.info("yahoo symbol search degraded to local results (%s): %s", query, exc)
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


