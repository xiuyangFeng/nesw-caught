import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemView
from app.services.stock_news_search import StockNewsSearchService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[WatchlistItemView])
def list_watchlist(session: Session = Depends(get_db_session)) -> list[WatchlistItemView]:
    repository = WatchlistRepository(session)
    return [WatchlistItemView.model_validate(item, from_attributes=True) for item in repository.list_all()]


@router.post("", response_model=WatchlistItemView, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistItemCreate,
    session: Session = Depends(get_db_session),
) -> WatchlistItemView:
    repository = WatchlistRepository(session)
    symbol = payload.symbol.upper()
    if repository.get_by_symbol(symbol):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="watchlist symbol already exists")

    item = repository.create(
        symbol=symbol,
        market=payload.market.lower(),
        display_name=payload.display_name.strip(),
        alert_threshold=payload.alert_threshold,
        alert_mode=payload.alert_mode,
    )

    search_service = StockNewsSearchService(session)
    matched = search_service.sync_match_existing(symbol, payload.display_name.strip(), payload.market.lower())
    logger.info("watchlist %s: sync matched %d existing news items", symbol, matched)

    settings = get_settings()
    if matched < settings.stock_news_min_count:
        search_service.trigger_async_external_search(symbol, payload.display_name.strip(), payload.market.lower())
        logger.info("watchlist %s: triggered async external news search (matched %d < threshold %d)", symbol, matched, settings.stock_news_min_count)

    return WatchlistItemView.model_validate(item, from_attributes=True)


@router.get("/{symbol}/related-news", response_model=list[NewsItemSummary])
def list_related_news(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> list[NewsItemSummary]:
    repository = NewsMentionsRepository(session)
    items = repository.list_related_news(symbol)
    return [NewsItemSummary.model_validate(item, from_attributes=True) for item in items]
