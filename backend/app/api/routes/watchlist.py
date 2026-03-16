from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemView

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
    return WatchlistItemView.model_validate(item, from_attributes=True)


@router.get("/{symbol}/related-news", response_model=list[NewsItemSummary])
def list_related_news(
    symbol: str,
    session: Session = Depends(get_db_session),
) -> list[NewsItemSummary]:
    repository = NewsMentionsRepository(session)
    items = repository.list_related_news(symbol)
    return [NewsItemSummary.model_validate(item, from_attributes=True) for item in items]
