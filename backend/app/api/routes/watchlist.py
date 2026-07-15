import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.schemas.watchlist import (
    WatchlistAiInsightView,
    WatchlistCandidateView,
    WatchlistItemCreate,
    WatchlistItemUpdate,
    WatchlistItemView,
    WatchlistResearchBriefView,
)
from app.services.llm_providers import build_provider
from app.services.quote_provider import equivalent_symbol_candidates, normalize_symbol
from app.services.stock_news_search import StockNewsSearchService
from app.services.watchlist_candidates import list_watchlist_candidates
from app.services.watchlist_research_service import WatchlistResearchService

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_watchlist_lookup_symbol(symbol: str) -> str:
    raw = symbol.upper()
    try:
        return normalize_symbol(raw).symbol
    except ValueError:
        return raw


def _resolve_watchlist_stored_symbol(symbol: str, repository: WatchlistRepository) -> str:
    for candidate in equivalent_symbol_candidates(symbol):
        if repository.get_by_symbol(candidate):
            return candidate
    return _normalize_watchlist_lookup_symbol(symbol)


def _candidate_symbols_for_conflict_check(symbol: str, market: str) -> list[str]:
    raw = symbol.upper()
    if market != "cn":
        return [raw]

    normalized = normalize_symbol(raw, market).symbol
    digits, suffix = normalized.split(".", 1)
    candidates = {raw, normalized, digits}
    if suffix == "SH":
        candidates.add(f"SH{digits}")
    if suffix == "SZ":
        candidates.add(f"SZ{digits}")
    return list(candidates)


@router.get("", response_model=list[WatchlistItemView])
def list_watchlist(session: Session = Depends(get_db_session)) -> list[WatchlistItemView]:
    repository = WatchlistRepository(session)
    return [WatchlistItemView.model_validate(item, from_attributes=True) for item in repository.list_all()]


@router.get("/candidates", response_model=list[WatchlistCandidateView])
def get_watchlist_candidates() -> list[WatchlistCandidateView]:
    return [WatchlistCandidateView.model_validate(item) for item in list_watchlist_candidates()]


@router.post("", response_model=WatchlistItemView, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistItemCreate,
    session: Session = Depends(get_db_session),
) -> WatchlistItemView:
    repository = WatchlistRepository(session)
    market = payload.market.lower()
    symbol = payload.symbol.upper()
    if market == "cn":
        try:
            symbol = normalize_symbol(symbol, market).symbol
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if any(repository.get_by_symbol(candidate) for candidate in _candidate_symbols_for_conflict_check(payload.symbol, market)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="watchlist symbol already exists")

    item = repository.create(
        symbol=symbol,
        market=market,
        display_name=payload.display_name.strip(),
        alert_threshold=payload.alert_threshold,
        alert_mode=payload.alert_mode,
    )

    search_service = StockNewsSearchService(session)
    matched = search_service.sync_match_existing(symbol, payload.display_name.strip(), market)
    logger.info("watchlist %s: sync matched %d existing news items", symbol, matched)

    settings = get_settings()
    if matched < settings.stock_news_min_count:
        search_service.trigger_async_external_search(symbol, payload.display_name.strip(), market)
        logger.info("watchlist %s: triggered async external news search (matched %d < threshold %d)", symbol, matched, settings.stock_news_min_count)

    return WatchlistItemView.model_validate(item, from_attributes=True)


@router.patch("/{symbol}", response_model=WatchlistItemView)
def update_watchlist_item(
    symbol: str,
    payload: WatchlistItemUpdate,
    session: Session = Depends(get_db_session),
) -> WatchlistItemView:
    """更新自选股持仓量 / 平均成本（持仓/组合视图）。

    仅写入请求体中显式给出的字段（exclude_unset），既有字段与行为保持不变。
    """
    repository = WatchlistRepository(session)
    resolved_symbol = _resolve_watchlist_stored_symbol(symbol, repository)
    updates = payload.model_dump(exclude_unset=True)
    item = repository.update_position(resolved_symbol, updates)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist symbol not found")
    return WatchlistItemView.model_validate(item, from_attributes=True)


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> None:
    repository = WatchlistRepository(session)
    deleted = repository.delete_by_symbol(_resolve_watchlist_stored_symbol(symbol, repository))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist symbol not found")


@router.get("/{symbol}/related-news", response_model=list[NewsItemSummary])
def list_related_news(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> list[NewsItemSummary]:
    watchlist_repository = WatchlistRepository(session)
    repository = NewsMentionsRepository(session)
    items = repository.list_related_news(_resolve_watchlist_stored_symbol(symbol, watchlist_repository))
    return [NewsItemSummary.model_validate(item, from_attributes=True) for item in items]


@router.get("/{symbol}/research-brief", response_model=WatchlistResearchBriefView)
def get_watchlist_research_brief(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> WatchlistResearchBriefView:
    return WatchlistResearchService().build_brief(_resolve_watchlist_stored_symbol(symbol, WatchlistRepository(session)), session)


@router.post("/{symbol}/ai-insight", response_model=WatchlistAiInsightView)
def get_watchlist_ai_insight(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> WatchlistAiInsightView:
    watchlist_repository = WatchlistRepository(session)
    resolved_symbol = _resolve_watchlist_stored_symbol(symbol, watchlist_repository)
    item = watchlist_repository.get_by_symbol(resolved_symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="watchlist symbol not found")

    news_mentions_repo = NewsMentionsRepository(session)
    news_items = news_mentions_repo.list_related_news(resolved_symbol)

    # Filter news from the last 7 days (maximum 10 items)
    now = datetime.now(UTC)
    limit_date = now - timedelta(days=7)
    recent_news = []
    for n in news_items:
        pub_time = n.published_at or n.fetched_at
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=UTC)
        if pub_time >= limit_date:
            recent_news.append(n)
            if len(recent_news) >= 10:
                break

    if not recent_news:
        return WatchlistAiInsightView(
            symbol=resolved_symbol,
            insight_text="暂无该股票的近期关联新闻，无法生成 AI 研判。",
            generated_at=datetime.now(UTC),
        )

    llm_repo = LLMProviderConfigRepository(session)
    llm_config = llm_repo.get_default()
    if llm_config is None:
        raise HTTPException(status_code=400, detail="llm provider is not configured")

    provider = build_provider(llm_config)

    news_lines = []
    for idx, n in enumerate(recent_news, 1):
        news_lines.append(
            f"{idx}. 时间: {n.published_at or n.fetched_at} | 来源: {n.source_name}\n"
            f"   标题: {n.title}\n"
            f"   摘要: {n.summary or '无'}"
        )
    news_list_str = "\n".join(news_lines)

    system_prompt = (
        "你是一个专业的证券投研专家。请分析用户提供的最新个股关联新闻，"
        "并给出一份详实、客观、结构化（使用 Markdown 格式）的研判简报。请严格按照以下几个模块输出，切忌空话和重复描述：\n\n"
        "1. **核心利好梳理**：概括新闻中提及的有利因素、业绩提振点或公司发展红利。\n"
        "2. **核心利空与潜在风险**：梳理宏观政策扰动、竞争加剧或产业链供应链警报。\n"
        "3. **后市策略研判**：\n"
        "   - 短期情绪：评估消息面对股价短期波动的正面或负面拉动。\n"
        "   - 中长期基本面：结合基本面 read-through，给出中长期展望建议。\n\n"
        "要求：段落清晰，条理分明，利于看盘者快速脱水和做出策略决定。"
    )

    user_prompt = (
        f"个股: {item.display_name} ({resolved_symbol})\n\n"
        f"关联新闻列表如下:\n{news_list_str}"
    )

    try:
        insight_text = provider.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}") from exc

    failover_info = provider.failover_triggered
    return WatchlistAiInsightView(
        symbol=resolved_symbol,
        insight_text=insight_text,
        generated_at=datetime.now(UTC),
        failover=failover_info
    )
