import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.services.event_bus import build_event_bus, get_event_bus, set_event_bus
from app.services.market_quote_producer import MarketQuoteProducer
from app.services.news_ingest_scheduler import NewsIngestScheduler
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.services.notification_service import get_notification_service
from app.services.quote_service import QuoteService
from app.services.cleanup import build_data_cleanup_worker
from app.services.news_dedup import configure_secondary_judge_from_settings

logger = logging.getLogger(__name__)


from app.workers.queue_worker import BackgroundQueueWorker, analysis_queue


def get_quote_service() -> QuoteService:
    return QuoteService()


def _register_event_handlers() -> None:
    event_bus = build_event_bus()

    def handle_news_created_batch(payload: dict[str, object]) -> None:
        raw_ids = payload.get("news_ids") if isinstance(payload, dict) else None
        if not isinstance(raw_ids, list):
            return
        news_ids = [int(item) for item in raw_ids]
        if not news_ids:
            return
        analysis_queue.put(news_ids)

    def handle_news_analysis_completed(payload: dict[str, object]) -> None:
        get_notification_service().on_analysis_completed(payload)

    event_bus.subscribe("news.created_batch", handle_news_created_batch)
    event_bus.subscribe("news.analysis_completed", handle_news_analysis_completed)
    set_event_bus(event_bus)

    # Register route-level cache invalidation on the finalized bus instance.
    # Doing this at module import time would bind the handlers to a stale bus
    # that gets replaced by set_event_bus above.
    from app.api.routes.news import register_cache_invalidation

    register_cache_invalidation(event_bus)


def register_market_watchlist_handlers(event_bus: Any) -> None:
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

    event_bus.subscribe("market.watchlist_refreshed", handle_market_watchlist_refreshed)


def build_market_quote_producer(event_bus: Any | None = None) -> MarketQuoteProducer:
    settings = get_settings()
    return MarketQuoteProducer(
        session_factory=SessionLocal,
        quote_service_factory=get_quote_service,
        event_bus=event_bus or get_event_bus(),
        poll_interval_seconds=settings.market_quote_poll_interval_seconds,
        logger=logger,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.core.auth import init_app_token
    init_app_token()
    initialize_database()
    configure_secondary_judge_from_settings()
    _register_event_handlers()
    notification_service = get_notification_service()
    notification_service.start()

    # Start queue worker for async pipeline processing
    queue_worker = BackgroundQueueWorker(session_factory=SessionLocal)
    queue_worker.start()

    settings = get_settings()
    news_scheduler: NewsIngestScheduler | None = None
    cleanup_worker = None
    digest_worker = None
    if settings.digest_enabled:
        from app.workers.digest_worker import DigestWorker

        def _run_digest(market_scope: str, phase: str) -> None:
            from app.services.digest_service import generate_digest

            with SessionLocal() as session:
                digest = generate_digest(market_scope, session)
            get_notification_service().on_digest_ready(digest.to_payload())

        digest_worker = DigestWorker(
            session_factory=SessionLocal,
            trigger_fn=_run_digest,
            premarket_time=settings.digest_premarket_time,
            postmarket_time=settings.digest_postmarket_time,
            logger=logger,
        )
        digest_worker.start()
    if settings.news_scheduler_enabled:
        news_scheduler = NewsIngestScheduler(
            session_factory=SessionLocal,
            tick_seconds=settings.news_scheduler_tick_seconds,
            max_backoff_multiplier=settings.news_backoff_max_multiplier,
        )
        news_scheduler.start()
    if settings.data_cleanup_enabled:
        cleanup_worker = build_data_cleanup_worker(SessionLocal)
        cleanup_worker.start()

    # Periodic fallback flush for the token usage buffer: without it, buffered
    # rows below flush_n could linger in memory indefinitely on low traffic.
    from app.services.token_usage_buffer import token_usage_buffer

    async def _flush_token_usage_periodically() -> None:
        while True:
            await asyncio.sleep(token_usage_buffer.flush_interval_seconds)
            token_usage_buffer.flush()

    token_flush_task = asyncio.create_task(_flush_token_usage_periodically())
    yield
    token_flush_task.cancel()
    try:
        await token_flush_task
    except asyncio.CancelledError:
        pass
    if digest_worker is not None:
        digest_worker.stop()
    if cleanup_worker is not None:
        cleanup_worker.stop()
    if news_scheduler is not None:
        news_scheduler.stop()
    queue_worker.stop()
    notification_service.stop()
    from app.services.http_pool import aclose_async_llm_client, close_llm_client
    close_llm_client()
    await aclose_async_llm_client()
    token_usage_buffer.flush()


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
