import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.schemas.watchlist import WatchlistCandidateView, WatchlistItemCreate, WatchlistItemView, WatchlistResearchBriefView
from app.services.quote_provider import equivalent_symbol_candidates, normalize_symbol
from app.services.stock_news_search import StockNewsSearchService
from app.services.watchlist_research_service import WatchlistResearchService
from app.services.watchlist_candidates import list_watchlist_candidates

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
