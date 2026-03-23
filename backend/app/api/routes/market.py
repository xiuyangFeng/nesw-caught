from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
    quotes = service.refresh_watchlist_quotes(session)
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
        triggered_at=datetime.now(timezone.utc),
    )
