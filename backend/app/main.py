from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.event_bus import build_event_bus, set_event_bus
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.services.notification_service import get_notification_service


def _register_event_handlers() -> None:
    event_bus = build_event_bus()

    def handle_news_created_batch(payload: dict[str, object]) -> None:
        raw_ids = payload.get("news_ids") if isinstance(payload, dict) else None
        if not isinstance(raw_ids, list):
            return
        news_ids = [int(item) for item in raw_ids]
        if not news_ids:
            return
        with SessionLocal() as session:
            summary = NewsSignalPipelineService(session).process_news_ids(news_ids)
            session.commit()
        if summary.processed_count > 0:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": summary.news_ids, "processed_count": summary.processed_count},
            )

    def handle_news_created_notifications(payload: dict[str, object]) -> None:
        raw_ids = payload.get("news_ids") if isinstance(payload, dict) else None
        if not isinstance(raw_ids, list):
            return
        news_ids = [int(item) for item in raw_ids]
        if not news_ids:
            return
        with SessionLocal() as session:
            repo = NewsRepository(session)
            notification_service = get_notification_service()
            for news_id in news_ids:
                item = repo.get_by_id(news_id)
                if item is None:
                    continue
                notification_service.on_news_created(
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source_name": item.source_name,
                        "market": item.market,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                    }
                )

    def handle_news_analysis_completed(payload: dict[str, object]) -> None:
        get_notification_service().on_analysis_completed(payload)

    def handle_market_watchlist_refreshed(payload: dict[str, object]) -> None:
        raw_quotes = payload.get("quotes") if isinstance(payload, dict) else None
        if not isinstance(raw_quotes, list):
            return
        with SessionLocal() as session:
            watchlist_items = {item.symbol: item for item in WatchlistRepository(session).list_all()}
        notification_service = get_notification_service()
        for quote in raw_quotes:
            if not isinstance(quote, dict):
                continue
            symbol = quote.get("symbol")
            if not symbol:
                continue
            watchlist_item = watchlist_items.get(str(symbol))
            if watchlist_item is None or not watchlist_item.alert_threshold:
                continue
            notification_service.on_watchlist_alert(
                {
                    "symbol": symbol,
                    "display_name": quote.get("display_name") or watchlist_item.display_name,
                    "price": quote.get("price"),
                    "change_percent": quote.get("change_percent"),
                    "alert_threshold": watchlist_item.alert_threshold,
                }
            )

    event_bus.subscribe("news.created_batch", handle_news_created_batch)
    event_bus.subscribe("news.created_batch", handle_news_created_notifications)
    event_bus.subscribe("news.analysis_completed", handle_news_analysis_completed)
    event_bus.subscribe("market.watchlist_refreshed", handle_market_watchlist_refreshed)
    set_event_bus(event_bus)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    _register_event_handlers()
    notification_service = get_notification_service()
    notification_service.start()
    yield
    notification_service.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
