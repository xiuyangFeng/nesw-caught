import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.market_repository import MarketRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.market import PriceSnapshotView, QuoteDetailView, QuoteSummaryView
from app.services.notification_service import get_notification_service
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
        watchlist_repo = WatchlistRepository(session)
        watchlist_items = {item.symbol: item for item in watchlist_repo.list_all()}
        ns = get_notification_service()
        for q in quotes:
            symbol = q.get("symbol")
            change_pct = q.get("change_percent")
            wl = watchlist_items.get(symbol) if symbol else None
            if wl and wl.alert_threshold:
                ns.on_watchlist_alert({
                    "symbol": symbol,
                    "display_name": q.get("display_name") or wl.display_name,
                    "price": q.get("price"),
                    "change_percent": change_pct,
                    "alert_threshold": wl.alert_threshold,
                })
    except Exception:
        logger.exception("failed to check watchlist alerts for notification")

    return [QuoteSummaryView.model_validate(item) for item in quotes]


@router.get("/symbols/{symbol}", response_model=QuoteDetailView)
def get_symbol_quote(symbol: str, session: Session = Depends(get_db_session)) -> QuoteDetailView:
    service = get_quote_service()
    return QuoteDetailView.model_validate(service.get_symbol_quote(symbol, session))
