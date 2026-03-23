import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.market_repository import MarketRepository
from app.schemas.market import PriceSnapshotView, QuoteDetailView, QuoteSummaryView
from app.services.event_bus import get_event_bus
from app.services.quote_service import QuoteService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_quote_service() -> QuoteService:
    return QuoteService()


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
    quotes = service.get_watchlist_quotes(session)

    try:
        get_event_bus().publish("market.watchlist_refreshed", {
            "symbols": [str(q.get("symbol")) for q in quotes if q.get("symbol")],
            "quotes": quotes,
        })
    except Exception:
        logger.exception("failed to publish watchlist refresh event")

    return [QuoteSummaryView.model_validate(item) for item in quotes]


@router.get("/symbols/{symbol}", response_model=QuoteDetailView)
def get_symbol_quote(symbol: str, session: Session = Depends(get_db_session)) -> QuoteDetailView:
    service = get_quote_service()
    return QuoteDetailView.model_validate(service.get_symbol_quote(symbol, session))
