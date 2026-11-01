import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_logging import RequestLoggingMiddleware
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.repositories.news_repository import NewsRepository  # noqa: F401 -- monkeypatched by tests
from app.services.alert_service import get_alert_service
from app.services.backup import build_backup_worker
from app.services.cleanup import build_data_cleanup_worker
from app.services.event_bus import build_event_bus, get_event_bus, set_event_bus
from app.services.market_overview_producer import MarketOverviewProducer
from app.services.market_quote_producer import MarketQuoteProducer
from app.services.news_dedup import configure_secondary_judge_from_settings
from app.services.news_ingest_scheduler import NewsIngestScheduler
from app.services.news_signal_pipeline import (  # noqa: F401 -- monkeypatched by tests
    NewsSignalPipelineService,
)
from app.services.quote_service import QuoteService
from app.workers.queue_worker import (
    BackgroundQueueWorker,
    OrphanQueueDrainWorker,
    analysis_queue,
)
from app.workers.takeaway_worker import TakeawayWorker

logger = logging.getLogger(__name__)


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

    if get_settings().pipeline_workers_enabled:
        # 多进程形态（pipeline_workers_enabled=false）下本进程没有 analysis_queue
        # 的消费者，注册这个 handler 只会往一个没人读的队列里堆数据。真正的消费
        # 在独立 pipeline worker 进程里：那边有自己的 RedisStreamConsumer + 同名
        # handler，加上 queue worker 每 30s 的 DB 兜底扫描双保险。
        event_bus.subscribe("news.created_batch", handle_news_created_batch)
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
        # 站内提醒：持仓股 |涨跌幅| 超阈值（默认 5%）每个交易日提醒一次；顺带推进关注股新闻合并窗口。
        try:
            get_alert_service().on_quotes([quote for quote in raw_quotes if isinstance(quote, dict)])
        except Exception:
            logger.exception("price alert evaluation failed")

    event_bus.subscribe("market.watchlist_refreshed", handle_market_watchlist_refreshed)


def build_market_quote_producer(event_bus: Any | None = None) -> MarketQuoteProducer:
    settings = get_settings()
    return MarketQuoteProducer(
        session_factory=SessionLocal,
        quote_service_factory=get_quote_service,
        event_bus=event_bus or get_event_bus(),
        poll_interval_seconds=settings.market_quote_poll_interval_seconds,
        idle_poll_interval_seconds=settings.market_quote_idle_poll_interval_seconds,
        logger=logger,
    )


def build_market_overview_producer() -> MarketOverviewProducer:
    settings = get_settings()
    return MarketOverviewProducer(
        session_factory=SessionLocal,
        poll_interval_seconds=settings.market_overview_poll_interval_seconds,
        idle_poll_interval_seconds=settings.market_overview_idle_poll_interval_seconds,
        logger=logger,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    # anyio 默认线程池只有 40 个 token，而本项目几乎所有路由都是同步 def
    # （FastAPI 会把它们丢进这个线程池），再叠加后台 worker 里的 to_thread 调用，
    # 40 很容易被吃满，表现为请求排队、"点一下几秒没反应"。这里按配置抬高上限。
    # 必须放在 lifespan 内：current_default_thread_limiter() 需要一个运行中的循环。
    import anyio.to_thread

    try:
        anyio.to_thread.current_default_thread_limiter().total_tokens = (
            get_settings().server_threadpool_size
        )
    except Exception:  # pragma: no cover - 不让线程池调优失败阻断启动
        logger.warning("failed to raise anyio default thread limiter", exc_info=True)

    from app.core.auth import init_app_token
    init_app_token()

    settings = get_settings()
    # 进程归属声明刻意打在 initialize_database() **之前**：alembic 会在迁移时执行
    # `fileConfig(alembic.ini)`，把 root logger 的 level 压到 WARNING 并换掉 handler，
    # 之后本进程的所有 INFO 都会被吞掉（既有问题，见报告的遗留项）。这条日志是
    # 「两个进程都开着 worker」这类误配置的主要可发现性手段，必须保证它一定能打出来。
    if settings.pipeline_workers_enabled:
        # 单机单进程默认形态（README 推荐）：重活 worker 随 web 进程一起启停。
        logger.info(
            "pipeline workers mode: IN-PROCESS (PIPELINE_WORKERS_ENABLED=true) — "
            "BackgroundQueueWorker/TakeawayWorker跑在 web 进程里；"
            "如需把它们移出 GIL，请设 PIPELINE_WORKERS_ENABLED=false 并单独运行 "
            "`python -m app.workers.pipeline_worker_main`"
        )
    else:
        # 多进程形态：本进程只做 web + ingestion，重活交给独立进程。
        # 这条 INFO 与独立入口的 ensure_exclusive_ownership() 互为对照：
        # 独立进程侧同时打出「exclusive ownership OK」才说明两边配置一致。
        logger.info(
            "pipeline workers mode: OUT-OF-PROCESS (PIPELINE_WORKERS_ENABLED=false) — "
            "本进程不启动 BackgroundQueueWorker/TakeawayWorker；"
            "请确保 `python -m app.workers.pipeline_worker_main` 正在运行，否则"
            "新闻只会入库、不会被评分"
        )

    initialize_database()
    configure_secondary_judge_from_settings()
    _register_event_handlers()
    # 情绪-价格背离周期检查（默认关闭）：命中写入站内提醒。
    divergence_worker = None
    if settings.sentiment_divergence_alert_enabled:
        from app.workers.queue_worker import SentimentDivergenceAlertWorker

        divergence_worker = SentimentDivergenceAlertWorker(
            session_factory=SessionLocal,
            alert_service=get_alert_service(),
        )
        divergence_worker.start()

    queue_worker: BackgroundQueueWorker | None = None
    takeaway_worker: TakeawayWorker | None = None
    orphan_queue_drainer: OrphanQueueDrainWorker | None = None
    if settings.pipeline_workers_enabled:
        # Start queue worker for async pipeline processing
        queue_worker = BackgroundQueueWorker(session_factory=SessionLocal)
        queue_worker.start()

        takeaway_worker = TakeawayWorker(session_factory=SessionLocal)
        takeaway_worker.start()
    elif settings.orphan_queue_drain_interval_seconds > 0:
        # 多进程形态：scheduler（仍在本进程）与 feed layout（请求线程）还会往
        # analysis_queue / takeaway_queue 里塞数据，而本进程已经没有消费者了。
        orphan_queue_drainer = OrphanQueueDrainWorker(session_factory=SessionLocal)
        orphan_queue_drainer.start()

    news_scheduler: NewsIngestScheduler | None = None
    cleanup_worker = None
    backup_worker = None
    digest_worker = None
    redis_consumer = None
    market_quote_producer: MarketQuoteProducer | None = None
    market_overview_producer: MarketOverviewProducer | None = None
    event_bus = get_event_bus()
    redis_publisher = getattr(event_bus, "redis_publisher", None)
    stream_map = getattr(event_bus, "stream_map", None) or {}
    publisher_id = getattr(event_bus, "publisher_id", None)
    inject_fn = getattr(event_bus, "inject_from_remote", None)
    if (
        settings.event_bus_backend in {"hybrid", "redis"}
        and redis_publisher is not None
        and callable(inject_fn)
        and stream_map
    ):
        from app.services.redis_stream_bus import RedisStreamConsumer

        stream_names = list(dict.fromkeys(stream_map.values()))
        redis_consumer = RedisStreamConsumer(
            redis_url=settings.redis_url,
            streams=stream_names,
            inject=inject_fn,
            timeout_seconds=settings.event_bus_publish_timeout_seconds,
            publisher_id=publisher_id,
        )
        redis_consumer.start()
        logger.info("redis stream consumer started for streams=%s", stream_names)
    if settings.digest_enabled:
        from app.workers.digest_worker import DigestWorker

        def _run_digest(market_scope: str, phase: str) -> None:
            from app.services.digest_service import generate_digest

            with SessionLocal() as session:
                generate_digest(market_scope, session)

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
    if settings.market_quote_producer_enabled:
        # 单机单进程默认形态:自选股行情 producer 与告警 handler 都随后端进程
        # 一起起停。多进程部署把该开关关掉,改用独立入口
        # `app.workers.market_quote_producer`（其 main() 会自行注册 handler）。
        register_market_watchlist_handlers(event_bus)
        market_quote_producer = build_market_quote_producer(event_bus)
        market_quote_producer.start()
    if settings.market_overview_producer_enabled:
        # 市场总览（指数/ETF + 东财板块缓存）轮询 producer，与自选股 producer
        # 完全独立、不发 event_bus 事件。多进程部署关掉该开关，改用独立入口
        # `app.workers.market_overview_producer`。
        market_overview_producer = build_market_overview_producer()
        market_overview_producer.start()
    if settings.data_cleanup_enabled:
        cleanup_worker = build_data_cleanup_worker(SessionLocal)
        cleanup_worker.start()
    if settings.backup_enabled:
        backup_worker = build_backup_worker(SessionLocal)
        if backup_worker is not None:
            backup_worker.start()

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
    if redis_consumer is not None:
        redis_consumer.stop()
    if digest_worker is not None:
        digest_worker.stop()
    if cleanup_worker is not None:
        cleanup_worker.stop()
    if backup_worker is not None:
        backup_worker.stop()
    if news_scheduler is not None:
        news_scheduler.stop()
    if market_quote_producer is not None:
        market_quote_producer.stop()
    if market_overview_producer is not None:
        market_overview_producer.stop()
    if queue_worker is not None:
        queue_worker.stop()
    if takeaway_worker is not None:
        takeaway_worker.stop()
    if orphan_queue_drainer is not None:
        orphan_queue_drainer.stop()
    if divergence_worker is not None:
        divergence_worker.stop()
    # 这里刻意用 close_llm_client()（关闭 + 允许惰性重建）而不是 shutdown_http_pools()
    # 的终态语义。终态是进程级且不可逆的，而 lifespan 在同一进程里会跑多次：
    # 测试用 `with TestClient(app)` 反复起停，且大量测试用不带 context manager 的
    # TestClient（**只触发 shutdown、不触发 startup**），所以"启动时解除终态"补不回来
    # —— 实测会让后续所有 LLM 调用抛 HttpPoolShutdownError 而非真实的下游错误。
    # 终态入口保留给确定不再复用进程的独立 worker 入口（app.workers.* 的 main）。
    from app.services.http_pool import aclose_async_llm_client, close_llm_client
    await aclose_async_llm_client()
    close_llm_client()
    token_usage_buffer.flush()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        file_enabled=settings.log_file_enabled,
        file_path=settings.log_file_path,
        file_max_bytes=settings.log_file_max_bytes,
        file_backup_count=settings.log_file_backup_count,
        log_format=settings.log_format,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        # /docs /redoc /openapi.json 挂在 api_router 下（见 app/api/router.py），
        # 使其继承 verify_app_token 鉴权；这里关闭 FastAPI 内置的免鉴权版本。
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    app.add_middleware(
        RequestLoggingMiddleware,
        access_log_enabled=settings.access_log_enabled,
        exclude_prefixes=tuple(
            prefix.strip()
            for prefix in settings.access_log_exclude_prefixes.split(",")
            if prefix.strip()
        ),
    )
    return app


app = create_app()
