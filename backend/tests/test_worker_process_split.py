"""第一轮优化：把后台重活 worker 移出 web 进程。

覆盖点（与工单一一对应）：
1. `PIPELINE_WORKERS_ENABLED` 对 lifespan 的开关语义（默认 true 不回退）；
2. 独立入口的可测装配（build_* / run，而不是只能真跑的 main）；
3. 跨进程事件通路：远端事件注入本地总线 → news_ids 进入本进程 analysis_queue；
4. 事件通路完全不工作时，queue worker 的 DB 兜底扫描仍能捞到 pending；
5. 优雅退场：停止信号后 worker 被 stop 且不抛异常；
6. 互斥保护：「两个进程都开着 worker」这种误配置必须可被发现。
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.models.news_item import NewsItem
from app.services import event_bus as event_bus_module
from app.workers import pipeline_worker_main
from app.workers import queue_worker as queue_worker_module
from app.workers.pipeline_worker_main import (
    PipelineWorkerConflictError,
    PipelineWorkerRuntime,
    build_pipeline_workers,
    build_runtime,
    ensure_exclusive_ownership,
    register_pipeline_event_handlers,
    run,
)
from app.workers.queue_worker import OrphanQueueDrainWorker, analysis_queue

# --------------------------------------------------------------------- 公共夹具


@pytest.fixture()
def memory_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _drain_module_queues():
    """模块级队列是进程内单例，用例之间必须清干净，避免互相污染。"""

    def _clear() -> None:
        from app.services.news_takeaway import takeaway_queue

        for target in (analysis_queue, takeaway_queue):
            while True:
                try:
                    target.get_nowait()
                except queue.Empty:
                    break
                target.task_done()

    _clear()
    yield
    _clear()


class _StubWorker:
    """记录 start/stop 调用次数的 worker 替身。"""

    def __init__(self, worker_name: str = "stub") -> None:
        self.worker_name = worker_name
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1


# ------------------------------------------------ 1. lifespan 的进程归属开关


def _run_lifespan(monkeypatch: pytest.MonkeyPatch, *, pipeline_workers_enabled: bool):
    """跑一次完整 lifespan，返回被拦截的 worker 替身。

    只替换需要断言的三个 worker 类；其余组件用 env 关掉，避免测试里起真实的
    调度器 / 备份 / 行情轮询线程。
    """
    from app import main as main_module

    created: dict[str, list[_StubWorker]] = {
        "queue": [],
        "takeaway": [],
        "drainer": [],
    }

    def _factory(bucket: str, name: str):
        def _build(*_args, **_kwargs):
            stub = _StubWorker(name)
            created[bucket].append(stub)
            return stub

        return _build

    monkeypatch.setattr(main_module, "BackgroundQueueWorker", _factory("queue", "background_queue_worker"))
    monkeypatch.setattr(main_module, "TakeawayWorker", _factory("takeaway", "takeaway_worker"))
    monkeypatch.setattr(main_module, "OrphanQueueDrainWorker", _factory("drainer", "orphan_queue_drainer"))

    monkeypatch.setenv("PIPELINE_WORKERS_ENABLED", "true" if pipeline_workers_enabled else "false")
    # 关掉与本用例无关、会起线程/发网络请求的组件。
    monkeypatch.setenv("EVENT_BUS_BACKEND", "memory")
    monkeypatch.setenv("MARKET_QUOTE_PRODUCER_ENABLED", "false")
    monkeypatch.setenv("DATA_CLEANUP_ENABLED", "false")
    monkeypatch.setenv("BACKUP_ENABLED", "false")
    monkeypatch.setenv("NEWS_SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()

    async def _cycle() -> None:
        async with main_module.lifespan(None):
            pass

    try:
        asyncio.run(_cycle())
    finally:
        get_settings.cache_clear()
    return created


def test_lifespan_starts_pipeline_workers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认（单机单进程推荐形态）行为不能回退。"""
    created = _run_lifespan(monkeypatch, pipeline_workers_enabled=True)

    assert len(created["queue"]) == 1
    assert len(created["takeaway"]) == 1
    assert created["queue"][0].start_count == 1
    assert created["takeaway"][0].start_count == 1
    # 进程内消费者存在时，不需要「无消费者队列」回收器。
    assert created["drainer"] == []
    # 关停路径同样要覆盖到。
    assert created["queue"][0].stop_count == 1
    assert created["takeaway"][0].stop_count == 1


def test_lifespan_skips_pipeline_workers_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    created = _run_lifespan(monkeypatch, pipeline_workers_enabled=False)

    assert created["queue"] == []
    assert created["takeaway"] == []
    # 生产者（scheduler / feed layout）仍在 web 进程里，必须有人回收这两个孤儿队列。
    assert len(created["drainer"]) == 1
    assert created["drainer"][0].start_count == 1
    assert created["drainer"][0].stop_count == 1


def test_web_process_skips_local_queue_handler_when_pipeline_is_out_of_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关掉进程内 worker 后，web 进程不再把 news_ids 塞进没人消费的本地队列。"""
    from app import main as main_module

    monkeypatch.setenv("PIPELINE_WORKERS_ENABLED", "false")
    monkeypatch.setenv("EVENT_BUS_BACKEND", "memory")
    get_settings.cache_clear()
    try:
        main_module._register_event_handlers()
        bus = event_bus_module.get_event_bus()
        bus.publish("news.created_batch", {"news_ids": [1, 2, 3]})
        assert analysis_queue.qsize() == 0

        # 反向对照：开关打开时照常入队。
        monkeypatch.setenv("PIPELINE_WORKERS_ENABLED", "true")
        get_settings.cache_clear()
        main_module._register_event_handlers()
        event_bus_module.get_event_bus().publish("news.created_batch", {"news_ids": [4]})
        assert analysis_queue.get_nowait() == [4]
    finally:
        get_settings.cache_clear()


def test_orphan_queue_drainer_discards_both_in_process_queues(memory_session_factory) -> None:
    from app.services.news_takeaway import takeaway_queue

    analysis_queue.put([1, 2, 3])
    takeaway_queue.put([7, 8])

    dropped = OrphanQueueDrainWorker(
        session_factory=memory_session_factory, interval_seconds=60.0
    ).do_cycle()

    assert dropped == 5
    assert analysis_queue.qsize() == 0
    assert takeaway_queue.qsize() == 0


# ---------------------------------------------- 2. 独立入口的可测装配（build_*）


def test_build_runtime_wires_bus_handler_and_workers(
    monkeypatch: pytest.MonkeyPatch, memory_session_factory
) -> None:
    settings = Settings(event_bus_backend="memory", pipeline_workers_enabled=False)

    runtime = build_runtime(
        session_factory=memory_session_factory,
        settings=settings,
        install_event_bus=False,
    )

    assert isinstance(runtime, PipelineWorkerRuntime)
    assert isinstance(runtime.event_bus, event_bus_module.HybridEventBus)
    # 注册了 news.created_batch handler
    assert runtime.handler is not None
    # 两个重活 worker 都在
    names = {worker.worker_name for worker in runtime.workers}
    assert {"background_queue_worker", "takeaway_worker"} <= names
    # memory 后端下没有 redis 消费者（此时只剩 DB 兜底扫描这条路）
    assert runtime.redis_consumer is None


def test_build_redis_consumer_subscribes_mapped_streams() -> None:
    """hybrid 后端下必须真的建出一个订阅了全部 stream 的消费者。"""
    settings = Settings(event_bus_backend="hybrid")
    bus = event_bus_module.build_event_bus(settings)

    consumer = pipeline_worker_main.build_redis_consumer(bus, settings)

    assert consumer is not None
    assert set(consumer.streams) == set(bus.stream_map.values())
    # publisher_id 对齐，避免本进程自己发的事件被自己回环消费
    assert consumer.publisher_id == bus.publisher_id


def test_build_pipeline_workers_enables_takeaway_db_fallback() -> None:
    """独立进程里 takeaway_queue 没有生产者，必须打开 DB 兜底扫描。"""
    settings = Settings(takeaway_fallback_scan_interval_seconds=0.0)

    workers = {
        worker.worker_name: worker
        for worker in build_pipeline_workers(session_factory=lambda: None, settings=settings)
    }

    assert workers["takeaway_worker"].fallback_scan_interval_seconds > 0


# --------------------------------------------------- 3. 跨进程事件通路（注入）


def test_remote_event_injection_reaches_this_process_analysis_queue() -> None:
    """模拟 RedisStreamConsumer 把 web 进程发出的事件注入本进程总线。"""
    bus = event_bus_module.build_event_bus(Settings(event_bus_backend="memory"))
    register_pipeline_event_handlers(bus)

    # inject_from_remote 正是 RedisStreamConsumer 使用的注入入口。
    bus.inject_from_remote("news.created_batch", {"news_ids": [11, 22, 33]})

    assert analysis_queue.get_nowait() == [11, 22, 33]


def test_pipeline_event_handler_ignores_malformed_payloads() -> None:
    bus = event_bus_module.build_event_bus(Settings(event_bus_backend="memory"))
    handler = register_pipeline_event_handlers(bus)

    handler({})
    handler({"news_ids": None})
    handler({"news_ids": []})

    assert analysis_queue.qsize() == 0


# ------------------------------------------------------------ 4. DB 兜底扫描


def _insert_news(session_factory, *, signal_status: str | None = None) -> int:
    now = datetime.now(UTC)
    with session_factory() as session:
        item = NewsItem(
            source_name="unit-test",
            source_url="https://example.com/a",
            title="pending item",
            canonical_url="https://example.com/a",
            url_hash="hash-a",
            market="us",
            fetched_at=now,
            published_at=now,
            signal_status=signal_status,
        )
        session.add(item)
        session.commit()
        return item.id


def test_queue_worker_fallback_scan_still_finds_pending_without_any_event(
    monkeypatch: pytest.MonkeyPatch, memory_session_factory
) -> None:
    """事件通路完全不工作时的安全网：worker 仍能从 DB 捞到 pending。"""
    news_id = _insert_news(memory_session_factory)

    processed: list[list[int]] = []

    class _FakePipeline:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int) -> list[int]:
            from sqlalchemy import select

            stmt = select(NewsItem.id).where(NewsItem.signal_status.is_(None)).limit(limit)
            return list(self.session.scalars(stmt))

        def process_news_ids(self, news_ids: list[int]):
            processed.append(list(news_ids))
            for item in self.session.query(NewsItem).filter(NewsItem.id.in_(news_ids)):
                item.signal_status = "processed"
            return SimpleNamespace(news_ids=list(news_ids), processed_count=len(news_ids))

    monkeypatch.setattr(queue_worker_module, "NewsSignalPipelineService", _FakePipeline)
    monkeypatch.setattr(
        queue_worker_module,
        "get_event_bus",
        lambda: event_bus_module.HybridEventBus(backend="memory"),
    )
    monkeypatch.setattr(
        queue_worker_module,
        "get_notification_service",
        lambda: SimpleNamespace(on_news_created_batch=lambda payloads: None),
    )

    worker = queue_worker_module.BackgroundQueueWorker(
        session_factory=memory_session_factory,
        fallback_scan_interval_seconds=0.0,
        inflight=queue_worker_module.InflightLeaseRegistry(),
    )
    # 队列全空（事件通路不通），只能靠兜底扫描
    assert analysis_queue.qsize() == 0
    count = worker.do_cycle()

    assert processed == [[news_id]]
    assert count == 1


def test_takeaway_worker_db_fallback_picks_items_without_takeaway(
    memory_session_factory,
) -> None:
    """多进程模式下 takeaway_queue 没有生产者，兜底扫描必须能捞到候选。"""
    from app.workers.takeaway_worker import TakeawayWorker

    news_id = _insert_news(memory_session_factory, signal_status="processed")

    worker = TakeawayWorker(
        session_factory=memory_session_factory,
        fallback_scan_interval_seconds=60.0,
    )
    assert worker._fallback_scan(limit=10) == {news_id}
    # 节流生效：同一个间隔内第二次扫描直接返回空
    assert worker._fallback_scan(limit=10) == set()

    # 关闭时（单进程默认形态）不做任何 DB 扫描
    disabled = TakeawayWorker(
        session_factory=memory_session_factory, fallback_scan_interval_seconds=0.0
    )
    assert disabled._fallback_scan(limit=10) == set()


# ------------------------------------------------------------ 5. 优雅退场


def test_runtime_stop_stops_workers_and_consumer(monkeypatch: pytest.MonkeyPatch) -> None:
    consumer = _StubWorker("redis_consumer")
    workers = [_StubWorker("background_queue_worker"), _StubWorker("takeaway_worker")]
    runtime = PipelineWorkerRuntime(
        event_bus=event_bus_module.HybridEventBus(backend="memory"),
        workers=workers,
        redis_consumer=consumer,
    )
    shutdown_calls: list[int] = []
    monkeypatch.setattr(
        "app.services.http_pool.shutdown_http_pools", lambda: shutdown_calls.append(1)
    )

    runtime.start()
    runtime.stop()

    assert [worker.start_count for worker in workers] == [1, 1]
    assert [worker.stop_count for worker in workers] == [1, 1]
    assert consumer.start_count == 1 and consumer.stop_count == 1
    # 独立进程是确定不再复用的进程：这里用的是进程级终态入口
    assert shutdown_calls == [1]


def test_run_blocks_until_stop_event_then_shuts_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """发停止信号后 worker 被 stop、且不抛异常。"""
    workers = [_StubWorker("background_queue_worker")]
    runtime = PipelineWorkerRuntime(
        event_bus=event_bus_module.HybridEventBus(backend="memory"),
        workers=workers,
        redis_consumer=None,
    )
    monkeypatch.setattr("app.services.http_pool.shutdown_http_pools", lambda: None)

    stop_event = threading.Event()
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            run(runtime, stop_event=stop_event, with_signal_handlers=False)
        except BaseException as exc:  # pragma: no cover - 失败时才会命中
            errors.append(exc)

    thread = threading.Thread(target=_target)
    thread.start()
    for _ in range(200):
        if runtime.started:
            break
        threading.Event().wait(0.01)
    assert runtime.started is True

    stop_event.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []
    assert workers[0].stop_count == 1
    assert runtime.started is False


def test_stop_is_resilient_to_a_worker_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """单个 worker 停不下来不能阻断其余清理。"""

    class _Boom(_StubWorker):
        def stop(self) -> None:
            super().stop()
            raise RuntimeError("boom")

    bad = _Boom("bad")
    good = _StubWorker("good")
    monkeypatch.setattr("app.services.http_pool.shutdown_http_pools", lambda: None)
    runtime = PipelineWorkerRuntime(
        event_bus=event_bus_module.HybridEventBus(backend="memory"),
        workers=[bad, good],
        redis_consumer=None,
    )

    runtime.stop()

    assert good.stop_count == 1


# ------------------------------------------------------------ 6. 互斥保护


def test_ensure_exclusive_ownership_refuses_when_web_process_still_owns_workers() -> None:
    """核心不变式：租约不跨进程，两个进程都开 worker 必须被拦下。"""
    settings = Settings(pipeline_workers_enabled=True)

    with pytest.raises(PipelineWorkerConflictError) as excinfo:
        ensure_exclusive_ownership(settings)

    assert "PIPELINE_WORKERS_ENABLED" in str(excinfo.value)


def test_ensure_exclusive_ownership_can_be_forced_but_warns_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(pipeline_workers_enabled=True)

    with caplog.at_level(logging.WARNING, logger=pipeline_worker_main.__name__):
        conflicted = ensure_exclusive_ownership(settings, strict=False)

    assert conflicted is True
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert warnings, "强行启动时必须留下可被发现的 WARNING"
    assert "重复爬正文" in warnings[0].getMessage()


def test_ensure_exclusive_ownership_passes_and_logs_mode_when_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(pipeline_workers_enabled=False)

    with caplog.at_level(logging.INFO, logger=pipeline_worker_main.__name__):
        assert ensure_exclusive_ownership(settings) is False

    assert any("exclusive ownership OK" in record.getMessage() for record in caplog.records)


def test_main_refuses_to_start_on_conflicting_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() 里的检查必须发生在 initialize_database / run 之前。"""
    monkeypatch.setenv("PIPELINE_WORKERS_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(pipeline_worker_main, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(
        pipeline_worker_main,
        "initialize_database",
        lambda: pytest.fail("conflict 检查必须早于 DB 初始化"),
    )
    monkeypatch.setattr(
        pipeline_worker_main, "run", lambda *a, **k: pytest.fail("冲突配置下不应启动 worker")
    )
    try:
        with pytest.raises(PipelineWorkerConflictError):
            pipeline_worker_main.main([])
    finally:
        get_settings.cache_clear()


class _RecordCollector(logging.Handler):
    """直接挂在目标 logger 上的记录收集器。

    刻意不用 caplog：lifespan 里的 `initialize_database()` 会触发 alembic 的
    `fileConfig`，把 root logger 上的 handler（包括 pytest 注入的那个）整体换掉，
    caplog 因此会漏掉之后发生的记录。
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(True, "pipeline workers mode: IN-PROCESS"), (False, "pipeline workers mode: OUT-OF-PROCESS")],
)
def test_lifespan_logs_the_active_pipeline_mode(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, expected: str
) -> None:
    """web 进程侧的可发现性：日志必须明确说明当前 worker 跑在哪。"""
    from app import main as main_module

    collector = _RecordCollector()
    target_logger = logging.getLogger(main_module.__name__)
    previous_level = target_logger.level
    target_logger.setLevel(logging.INFO)
    target_logger.addHandler(collector)
    try:
        _run_lifespan(monkeypatch, pipeline_workers_enabled=enabled)
    finally:
        target_logger.removeHandler(collector)
        target_logger.setLevel(previous_level)

    assert any(expected in message for message in collector.messages)
    # 两种模式都要指向另一半的操作方式，误配置时才能被人看出来。
    assert any("pipeline_worker_main" in message for message in collector.messages)
