"""独立 pipeline worker 进程入口（把后台重活移出 web 进程）。

为什么要拆
----------
`BackgroundQueueWorker` 干的是「爬正文 + BeautifulSoup 解析 + LLM 分类」。其中
解析阶段是纯 CPU 且全程持有 GIL（本环境未装 lxml，退回 html.parser，实测
cpu/wall ≈ 1.00）。只要它和 uvicorn 跑在同一个进程里，爬取活跃期就必然和请求
线程抢 GIL —— 实测只读接口 `/api/news/runtime` 的 p50 从 1-2ms 恶化到 265ms。
把它搬到独立进程后，web 进程的 GIL 才真正干净。

怎么用
------
    # 1) 先把 web 进程里的同名 worker 关掉（**必须**，见下面的互斥说明）
    PIPELINE_WORKERS_ENABLED=false uvicorn app.main:app --app-dir backend ...
    # 2) 再起独立 worker 进程
    PIPELINE_WORKERS_ENABLED=false python -m app.workers.pipeline_worker_main

单机单进程仍是默认且推荐形态：不设 `PIPELINE_WORKERS_ENABLED` 时一切照旧，
本模块根本不需要被拉起。

互斥（本模块最关键的不变式）
----------------------------
`queue_worker.analysis_inflight` 是**进程内内存**租约表。web 进程和本进程各跑
一个 `BackgroundQueueWorker` 时，两边的租约互相看不见，同一批 news_id 会被
**两个进程重复爬正文 + 重复调 LLM**。因此 :func:`ensure_exclusive_ownership`
在启动时读取 `PIPELINE_WORKERS_ENABLED`，只要它还是 true 就直接**拒绝启动**并
打印修复指引（`--force` 可以强行越过，仅用于确知 web 进程未启动的场景）。

跨进程事件通路
--------------
ingestion（仍在 web 进程）落库后 publish `news.created_batch`，事件经 Redis
Stream 抵达本进程；本进程的 `RedisStreamConsumer` 把它注入本地总线，
:func:`register_pipeline_event_handlers` 注册的 handler 再把 news_ids 投进
**本进程的** `analysis_queue`。即使 Redis 整条链路挂掉，`BackgroundQueueWorker`
每 30s 的 DB 兜底扫描（`queue_worker_fallback_scan_interval_seconds`）仍会把
pending 捞出来 —— 这是本设计的安全网，任何时候都不要破坏它。
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.services.event_bus import HybridEventBus, build_event_bus, set_event_bus
from app.workers.base_worker import BaseWorker
from app.workers.queue_worker import BackgroundQueueWorker, analysis_queue
from app.workers.takeaway_worker import TakeawayWorker
from app.workers.x_health_probe_worker import build_x_health_probe_worker

logger = logging.getLogger(__name__)

# 多进程形态下，独立进程里的 TakeawayWorker 拿不到 feed layout 投递的队列消息，
# 只能靠 DB 兜底扫描。settings 里默认是 0（关闭，保单进程语义），这里给出独立
# 进程的兜底默认值；显式配置 `TAKEAWAY_FALLBACK_SCAN_INTERVAL_SECONDS` 时以配置为准。
DEFAULT_STANDALONE_TAKEAWAY_FALLBACK_SECONDS = 120.0


class PipelineWorkerConflictError(RuntimeError):
    """web 进程与本进程同时启动 pipeline worker 的误配置。"""


# --------------------------------------------------------------------- 互斥保护


def ensure_exclusive_ownership(
    settings: Settings | None = None,
    *,
    strict: bool = True,
    log: logging.Logger | None = None,
) -> bool:
    """确保「同一时刻只有一个进程跑 pipeline worker」这条不变式可被发现。

    返回 True 表示检测到冲突配置。`strict=True`（默认）时直接抛
    :class:`PipelineWorkerConflictError`，让误配置在启动瞬间就暴露，而不是变成
    线上悄悄翻倍的 LLM 账单。
    """
    settings = settings or get_settings()
    log = log or logger
    if not settings.pipeline_workers_enabled:
        log.info(
            "pipeline worker process: exclusive ownership OK "
            "(PIPELINE_WORKERS_ENABLED=false, web 进程不再启动同名 worker)"
        )
        return False

    message = (
        "PIPELINE_WORKERS_ENABLED 仍为 true：web 进程的 lifespan 也会启动 "
        "BackgroundQueueWorker/TakeawayWorker。in-flight 租约是进程内内存、不跨进程，"
        "两个进程会重复爬正文 + 重复调 LLM。请设置 PIPELINE_WORKERS_ENABLED=false "
        "并重启 web 进程后再拉起本进程（确知 web 进程未运行时可用 --force 越过）。"
    )
    if strict:
        log.error("pipeline worker process refused to start: %s", message)
        raise PipelineWorkerConflictError(message)
    log.warning("pipeline worker process started with a conflicting config: %s", message)
    return True


# --------------------------------------------------------------------- 组装零件


def register_pipeline_event_handlers(event_bus: HybridEventBus) -> Callable[[dict], None]:
    """把 `news.created_batch` 的 news_ids 投进**本进程**的 analysis_queue。

    与 `app.main._register_event_handlers` 里的同名 handler 语义一致，区别只在
    「本进程」三个字：事件来源是 RedisStreamConsumer 注入的远端事件（ingestion 跑
    在 web 进程），而队列是本进程的内存队列。返回 handler 便于测试断言/反注册。
    """

    def handle_news_created_batch(payload: dict[str, object]) -> None:
        raw_ids = payload.get("news_ids") if isinstance(payload, dict) else None
        if not isinstance(raw_ids, list):
            return
        news_ids = [int(item) for item in raw_ids]
        if not news_ids:
            return
        analysis_queue.put(news_ids)

    event_bus.subscribe("news.created_batch", handle_news_created_batch)
    return handle_news_created_batch


def build_redis_consumer(event_bus: HybridEventBus, settings: Settings | None = None):
    """构造订阅相关 stream 的 RedisStreamConsumer；后端非 redis/hybrid 时返回 None。

    判定条件与 `app.main.lifespan` 保持一致（同一段逻辑的进程外复刻）：只有真的
    拿到 redis publisher、stream_map 和 inject 入口时才启动消费者。
    """
    settings = settings or get_settings()
    redis_publisher = getattr(event_bus, "redis_publisher", None)
    stream_map = getattr(event_bus, "stream_map", None) or {}
    inject_fn = getattr(event_bus, "inject_from_remote", None)
    if (
        settings.event_bus_backend not in {"hybrid", "redis"}
        or redis_publisher is None
        or not callable(inject_fn)
        or not stream_map
    ):
        logger.warning(
            "pipeline worker process: redis stream consumer not started "
            "(backend=%s); 只能依赖 queue worker 每 %.0fs 的 DB 兜底扫描",
            settings.event_bus_backend,
            settings.queue_worker_fallback_scan_interval_seconds,
        )
        return None

    from app.services.redis_stream_bus import RedisStreamConsumer

    stream_names = list(dict.fromkeys(stream_map.values()))
    return RedisStreamConsumer(
        redis_url=settings.redis_url,
        streams=stream_names,
        inject=inject_fn,
        timeout_seconds=settings.event_bus_publish_timeout_seconds,
        publisher_id=getattr(event_bus, "publisher_id", None),
    )


def build_pipeline_workers(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
) -> list[BaseWorker]:
    """构造本进程要跑的 worker 列表。"""
    settings = settings or get_settings()
    takeaway_fallback = settings.takeaway_fallback_scan_interval_seconds
    if takeaway_fallback <= 0:
        takeaway_fallback = DEFAULT_STANDALONE_TAKEAWAY_FALLBACK_SECONDS

    workers: list[BaseWorker] = [
        BackgroundQueueWorker(session_factory=session_factory),
        TakeawayWorker(
            session_factory=session_factory,
            fallback_scan_interval_seconds=takeaway_fallback,
        ),
    ]
    # X 健康探针是纯外网探针，跟着 pipeline worker 一起离开 web 进程。
    probe = build_x_health_probe_worker(session_factory)
    if probe is not None:
        workers.append(probe)
    return workers


@dataclass
class PipelineWorkerRuntime:
    """独立进程的运行时装配结果（可单测，不需要真的把进程跑起来）。"""

    event_bus: HybridEventBus
    workers: list[BaseWorker]
    redis_consumer: object | None = None
    handler: Callable[[dict], None] | None = None
    started: bool = field(default=False, init=False)

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        if self.redis_consumer is not None:
            self.redis_consumer.start()
        for worker in self.workers:
            worker.start()
        logger.info(
            "pipeline worker process started: workers=%s redis_consumer=%s",
            [worker.worker_name for worker in self.workers],
            self.redis_consumer is not None,
        )

    def stop(self) -> None:
        """优雅退场：先停 worker，再停 Redis 消费者，最后回收 HTTP 连接池。"""
        for worker in self.workers:
            try:
                worker.stop()
            except Exception:  # pragma: no cover - 单个 worker 停不下来不该阻断其余清理
                logger.exception("failed to stop worker '%s'", worker.worker_name)
        if self.redis_consumer is not None:
            try:
                self.redis_consumer.stop()
            except Exception:  # pragma: no cover
                logger.exception("failed to stop redis stream consumer")
        self.started = False
        # 这里刻意用 shutdown_http_pools()（进程级终态，不可逆）而不是 app.main
        # lifespan 里的 close_llm_client()：lifespan 在同一进程里会被反复跑（测试
        # 用 TestClient 反复起停），终态会误伤后续调用；而本进程是确定不再复用的
        # 独立进程，终态正好能挡住关停后仍在跑的 daemon 线程静默重建连接池。
        from app.services.http_pool import shutdown_http_pools

        shutdown_http_pools()
        logger.info("pipeline worker process stopped")


def build_runtime(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
    install_event_bus: bool = True,
) -> PipelineWorkerRuntime:
    """完成「事件总线 + 跨进程通路 + worker」的全部装配（不启动）。"""
    settings = settings or get_settings()
    event_bus = build_event_bus(settings)
    if install_event_bus:
        # worker 内部通过 get_event_bus() 拿总线发 news.updated 等事件，
        # 必须把本进程构建的实例装进模块级单例。
        set_event_bus(event_bus)
    handler = register_pipeline_event_handlers(event_bus)
    redis_consumer = build_redis_consumer(event_bus, settings)
    workers = build_pipeline_workers(session_factory=session_factory, settings=settings)
    return PipelineWorkerRuntime(
        event_bus=event_bus,
        workers=workers,
        redis_consumer=redis_consumer,
        handler=handler,
    )


# ------------------------------------------------------------------- 进程主流程


def install_signal_handlers(stop_event: threading.Event) -> None:
    """SIGTERM / SIGINT → 置位 stop_event（非主线程注册失败时静默跳过）。"""

    def _handle(signum, _frame) -> None:  # pragma: no cover - 真实信号路径
        logger.info("pipeline worker process received signal %s, shutting down", signum)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle)
        except ValueError:  # pragma: no cover - 只在非主线程发生
            logger.debug("cannot install handler for signal %s outside main thread", sig)


def run(
    runtime: PipelineWorkerRuntime | None = None,
    *,
    stop_event: threading.Event | None = None,
    with_signal_handlers: bool = True,
) -> None:
    """启动 runtime 并阻塞到 stop_event 置位，然后优雅退场。"""
    runtime = runtime if runtime is not None else build_runtime()
    stop_event = stop_event if stop_event is not None else threading.Event()
    if with_signal_handlers:
        install_signal_handlers(stop_event)
    runtime.start()
    try:
        stop_event.wait()
    finally:
        runtime.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.workers.pipeline_worker_main",
        description="独立进程运行 BackgroundQueueWorker / TakeawayWorker / X 健康探针",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使 PIPELINE_WORKERS_ENABLED 仍为 true 也强行启动（只降级为 WARNING）",
    )
    args = parser.parse_args(argv)

    settings = get_settings()

    def _configure_logging() -> None:
        configure_logging(
            settings.log_level,
            file_enabled=settings.log_file_enabled,
            file_path=settings.log_file_path,
            file_max_bytes=settings.log_file_max_bytes,
            file_backup_count=settings.log_file_backup_count,
            log_format=settings.log_format,
        )

    _configure_logging()
    ensure_exclusive_ownership(settings, strict=not args.force)
    # initialize_database() 内部跑 alembic 时经 config.attributes["configure_logger"]
    # = False（app/db/initializer.py）阻止 fileConfig 接管日志配置，不再需要
    # 此前"迁移后摘 handler 再重配"的补救逻辑；回归测试见 test_logging_config.py。
    initialize_database()
    run(build_runtime(settings=settings))
    return 0


if __name__ == "__main__":  # pragma: no cover - 进程入口
    raise SystemExit(main())
