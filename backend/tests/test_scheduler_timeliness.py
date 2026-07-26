"""WS-6：调度器 / 后台 worker / 抓取时效性回归测试。

覆盖的问题（按严重度）：

- P0 跨轮重复消费：scheduler 每 tick 无条件把 `signal_status IS NULL` 的前 N 条
  塞进分析队列，而 `signal_status` 要等管线阶段 2b 提交后才写回；批次耗时 > tick
  时同一批 id 被反复投递 → 重复爬正文 + 双倍 LLM token。
- P1 单轮批大小无界（队列被无上限抽干）。
- P1 整批抓取栅栏（等最慢的源）+ 批尾才发事件。
- P1 http_pool 标量超时 / 关停后连接池静默复活。
- P2 commit 后 ORM 过期触发 N 次 refresh SELECT。
- P2 并发度硬编码。
- 不变量：LLM/网络调用不得发生在写事务内。
"""

from __future__ import annotations

import queue
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import delete, event, select

from app.core.config import Settings
from app.db.session import SessionLocal, engine
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.services import http_pool

# news_ingestion 必须先于 ingestion.service 导入：两者互相引用，只有从
# news_ingestion 这一侧进入才能正常完成循环导入。
from app.services import news_ingestion as _news_ingestion_module  # noqa: F401
from app.services import news_signal_pipeline as pipeline_module
from app.services.ingestion import service as ingestion_service_module
from app.services.ingestion.service import NewsIngestionService
from app.services.ingestion.types import (
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
)
from app.services.news_ingest_scheduler import NewsIngestScheduler
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.workers import queue_worker as queue_worker_module
from app.workers.queue_worker import (
    BackgroundQueueWorker,
    InflightLeaseRegistry,
    analysis_queue,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSession:
    def commit(self) -> None:
        return None


@contextmanager
def fake_session_factory():
    yield FakeSession()


@pytest.fixture(autouse=True)
def _clean_analysis_queue():
    """每个用例前后都清空共享的进程级分析队列，避免跨用例串味。"""
    def _drain() -> None:
        while True:
            try:
                analysis_queue.get_nowait()
                analysis_queue.task_done()
            except queue.Empty:
                return

    _drain()
    yield
    _drain()


# ---------------------------------------------------------------------------
# 1. P0 回归：跨轮重复消费
# ---------------------------------------------------------------------------


def _build_backlog_scheduler(monkeypatch, *, registry, clock, pending: list[int]):
    """构造一个"只做 backlog 投递"的 scheduler（无抓取源）。"""

    class FakePipelineService:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            # 模拟 signal_status 尚未写回：pending 列表始终不变。
            return list(pending)[:limit]

    monkeypatch.setattr(
        "app.services.news_ingest_scheduler.NewsSignalPipelineService", FakePipelineService
    )

    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=list,
        inflight=registry,
        clock=clock,
    )
    monkeypatch.setattr(scheduler, "_record_success", lambda *a, **k: None)
    monkeypatch.setattr(scheduler, "_record_failure", lambda *a, **k: None)
    return scheduler


def test_scheduler_does_not_reenqueue_ids_still_in_flight(monkeypatch) -> None:
    """批次耗时 > tick 时，同一批 news_id 不得被 scheduler 二次投递。

    修复前：`_drain_signal_backlog` 每 5s 无条件 put 一次前 50 条 pending，
    signal_status 要到管线阶段 2b commit 才变 "processed"，于是同一批 id 会被
    反复投递、下一轮整批重跑（重复爬正文 + 双倍 LLM token）。
    """
    clock = FakeClock()
    registry = InflightLeaseRegistry(lease_seconds=600.0, clock=clock)
    scheduler = _build_backlog_scheduler(monkeypatch, registry=registry, clock=clock, pending=[1, 2, 3])

    assert scheduler._drain_signal_backlog() == 3
    assert analysis_queue.get_nowait() == [1, 2, 3]
    analysis_queue.task_done()

    # 模拟 worker 领取后仍在处理（signal_status 未写回），scheduler 连跑 5 个 tick
    for _ in range(5):
        clock.advance(5.0)
        assert scheduler._drain_signal_backlog() == 0
    assert analysis_queue.qsize() == 0, "在租约内的 id 不得被重复投递"


def test_inflight_lease_expiry_allows_reenqueue(monkeypatch) -> None:
    """租约过期（worker 崩溃/卡死）后必须允许重投，否则会永久漏处理。"""
    clock = FakeClock()
    registry = InflightLeaseRegistry(lease_seconds=600.0, clock=clock)
    scheduler = _build_backlog_scheduler(monkeypatch, registry=registry, clock=clock, pending=[1, 2, 3])

    assert scheduler._drain_signal_backlog() == 3
    analysis_queue.get_nowait()
    analysis_queue.task_done()

    clock.advance(599.0)
    assert scheduler._drain_signal_backlog() == 0

    clock.advance(2.0)  # 越过 600s 租约
    assert scheduler._drain_signal_backlog() == 3
    assert analysis_queue.get_nowait() == [1, 2, 3]
    analysis_queue.task_done()


def test_worker_release_lets_scheduler_reenqueue_failed_items(monkeypatch) -> None:
    """worker 处理结束后立即释放租约：失败条目下一轮可以重试，不被锁死 600s。"""
    clock = FakeClock()
    registry = InflightLeaseRegistry(lease_seconds=600.0, clock=clock)
    scheduler = _build_backlog_scheduler(monkeypatch, registry=registry, clock=clock, pending=[7, 8])

    assert scheduler._drain_signal_backlog() == 2
    analysis_queue.get_nowait()
    analysis_queue.task_done()

    clock.advance(5.0)
    assert scheduler._drain_signal_backlog() == 0

    registry.release([7, 8])  # worker 处理完毕（成功或失败）
    clock.advance(5.0)
    assert scheduler._drain_signal_backlog() == 2


def test_inflight_registry_is_shared_between_scheduler_and_queue_worker() -> None:
    """租约状态必须放在两个组件都能看到的地方（模块级单例）。"""
    scheduler = NewsIngestScheduler(session_factory=fake_session_factory, sources_loader=list)
    worker = BackgroundQueueWorker(session_factory=fake_session_factory)
    assert scheduler.inflight is worker.inflight is queue_worker_module.analysis_inflight


# ---------------------------------------------------------------------------
# 2. P1：单轮批大小上限
# ---------------------------------------------------------------------------


def test_queue_worker_batch_is_capped_and_remainder_stays_queued() -> None:
    settings = Settings()
    limit = settings.news_signal_backlog_batch_size
    worker = BackgroundQueueWorker(session_factory=fake_session_factory)
    assert worker.batch_size == limit

    for news_id in range(1, 501):
        analysis_queue.put([news_id])

    batch = worker._drain_queue()

    assert len(batch) == limit
    assert len(set(batch)) == limit
    assert analysis_queue.qsize() == 500 - limit, "超出批上限的条目必须留在队列里"


def test_queue_worker_splits_oversized_chunk_and_pushes_remainder_back() -> None:
    worker = BackgroundQueueWorker(session_factory=fake_session_factory, batch_size=10)
    analysis_queue.put(list(range(100)))

    batch = worker._drain_queue()

    assert batch == list(range(10))
    leftover = analysis_queue.get_nowait()
    analysis_queue.task_done()
    assert leftover == list(range(10, 100))


# ---------------------------------------------------------------------------
# 3. P1：as_completed —— 慢源不再阻塞快源的落库与发事件
# ---------------------------------------------------------------------------


def _fake_inserted_item(news_id: int, source_name: str) -> SimpleNamespace:
    now = datetime(2026, 7, 25, 8, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=news_id,
        title=f"{source_name} headline",
        summary=None,
        source_name=source_name,
        canonical_url=f"https://example.com/{news_id}",
        market="us",
        sentiment_label=None,
        published_at=now,
        fetched_at=now,
        effective_at=now,
        editorial_score=None,
        ai_takeaway=None,
    )


def test_fast_source_persists_and_publishes_before_slow_source_returns(monkeypatch) -> None:
    """整批栅栏移除：`as_completed` 让先返回的源先落库、先发事件。

    修复前是 `[f.result() for f in futures]` + 批尾统一 publish，
    快源必须陪跑到最慢的源。
    """
    fast = SourceDefinition(name="fast", source_type="rss", url="https://fast.example/rss", market="us")
    slow = SourceDefinition(name="slow", source_type="rss", url="https://slow.example/rss", market="us")

    timeline: list[str] = []
    timeline_lock = threading.Lock()

    def record(tag: str) -> None:
        with timeline_lock:
            timeline.append(tag)

    slow_started = threading.Event()

    def fake_fetch(source, *, etag=None, last_modified=None):
        if source.name == "slow":
            slow_started.set()
            time.sleep(0.5)
            record("slow-fetch-returned")
        else:
            # 让慢源先真正开跑，确保测的是"快源不等慢源"而不是调度顺序巧合。
            slow_started.wait(timeout=1.0)
            record("fast-fetch-returned")
        return SourceFetchOutcome(source=source, items=[], error=None, latency_ms=1.0)

    monkeypatch.setattr(ingestion_service_module, "fetch_source_items", fake_fetch)

    class FakeHealthRepo:
        def get_or_create(self, **kwargs):
            return SimpleNamespace(last_etag=None, last_modified=None)

    class FakePersister:
        counter = 0

        def persist_outcome(self, outcome):
            FakePersister.counter += 1
            record(f"persist:{outcome.source.name}")
            return SourceFetchResult(
                source_name=outcome.source.name,
                source_type=outcome.source.source_type,
                status="ok",
                fetched_count=1,
                inserted_count=1,
                error=None,
                latency_ms=1.0,
                inserted_items=[_fake_inserted_item(FakePersister.counter, outcome.source.name)],
            )

    class RecordingBus:
        def publish(self, event_name, payload):
            if event_name == "news.created":
                record(f"publish:{payload['source_name']}")

    monkeypatch.setattr(ingestion_service_module.news_ingestion, "get_event_bus", lambda: RecordingBus())

    service = NewsIngestionService.__new__(NewsIngestionService)
    service.session = FakeSession()
    service.source_health_repository = FakeHealthRepo()
    service.persister = FakePersister()

    summary = service.refresh_all(sources=[slow, fast])

    assert summary.inserted_count == 2
    assert timeline.index("persist:fast") < timeline.index("slow-fetch-returned")
    assert timeline.index("publish:fast") < timeline.index("slow-fetch-returned")
    assert timeline.index("persist:slow") > timeline.index("slow-fetch-returned")


# ---------------------------------------------------------------------------
# 4. P2：启动抖动打散惊群
# ---------------------------------------------------------------------------


def test_startup_jitter_spreads_first_due_times() -> None:
    sources = [
        SourceDefinition(name=f"s{i}", source_type="rss", url=f"https://e{i}.example/rss", market="us")
        for i in range(12)
    ]
    clock = FakeClock()
    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=lambda: sources,
        startup_jitter_seconds=8.0,
        clock=clock,
    )

    # 施加抖动之前：全部源 next_due 都是 0.0 —— 进程重启后的惊群来源。
    assert all(scheduler._next_due_at.get(s.name, 0.0) == 0.0 for s in sources)

    due_at = scheduler.apply_startup_jitter()

    assert len(due_at) == len(sources)
    assert len(set(due_at.values())) > 1, "首次 due 必须被打散，不能全部相同"
    assert all(clock.now <= value < clock.now + 8.0 for value in due_at.values())
    # 抖动窗口内不会所有源同时到期
    assert len(scheduler.due_sources()) < len(sources)


def test_startup_jitter_disabled_keeps_all_sources_immediately_due() -> None:
    sources = [
        SourceDefinition(name=f"s{i}", source_type="rss", url=f"https://e{i}.example/rss", market="us")
        for i in range(3)
    ]
    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=lambda: sources,
        startup_jitter_seconds=0.0,
        clock=FakeClock(),
    )
    scheduler.apply_startup_jitter()
    assert len(scheduler.due_sources()) == 3


# ---------------------------------------------------------------------------
# 5. P2：并发度 / 批大小读配置生效（不再硬编码）
# ---------------------------------------------------------------------------


def test_fetch_max_workers_comes_from_settings(monkeypatch) -> None:
    captured: dict[str, int] = {}
    real_pool = ingestion_service_module.ThreadPoolExecutor

    class SpyPool(real_pool):
        def __init__(self, *args, max_workers=None, **kwargs):
            captured["max_workers"] = max_workers
            super().__init__(*args, max_workers=max_workers, **kwargs)

    monkeypatch.setattr(ingestion_service_module, "ThreadPoolExecutor", SpyPool)
    monkeypatch.setattr(
        ingestion_service_module,
        "get_settings",
        lambda: Settings(news_fetch_max_workers=3),
    )
    monkeypatch.setattr(
        ingestion_service_module,
        "fetch_source_items",
        lambda source, **kwargs: SourceFetchOutcome(source=source, items=[], error=None, latency_ms=0.0),
    )

    class FakeHealthRepo:
        def get_or_create(self, **kwargs):
            return SimpleNamespace(last_etag=None, last_modified=None)

    class NoopPersister:
        def persist_outcome(self, outcome):
            return SourceFetchResult(
                source_name=outcome.source.name,
                source_type=outcome.source.source_type,
                status="empty",
                fetched_count=0,
                inserted_count=0,
                error=None,
                latency_ms=0.0,
                inserted_items=[],
            )

    service = NewsIngestionService.__new__(NewsIngestionService)
    service.session = FakeSession()
    service.source_health_repository = FakeHealthRepo()
    service.persister = NoopPersister()

    sources = [
        SourceDefinition(name=f"s{i}", source_type="rss", url=f"https://e{i}.example/rss", market="us")
        for i in range(10)
    ]
    service.refresh_all(sources=sources)

    assert captured["max_workers"] == 3


def test_pipeline_concurrency_reads_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_module,
        "get_settings",
        lambda: Settings(news_crawl_max_workers=2, news_classify_max_workers=3),
    )
    assert pipeline_module._setting("news_crawl_max_workers", 8) == 2
    assert pipeline_module._setting("news_classify_max_workers", 4) == 3


def test_queue_worker_intervals_read_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        queue_worker_module,
        "get_settings",
        lambda: Settings(
            queue_worker_poll_interval_seconds=2.5,
            queue_worker_fallback_scan_interval_seconds=11.0,
            news_signal_backlog_batch_size=7,
        ),
    )
    worker = BackgroundQueueWorker(session_factory=fake_session_factory)
    assert worker.poll_interval_seconds == 2.5
    assert worker.get_interval() == 2.5
    assert worker.fallback_scan_interval_seconds == 11.0
    assert worker.batch_size == 7


def test_scheduler_backlog_batch_size_reads_settings(monkeypatch) -> None:
    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=list,
        backlog_batch_size=9,
    )
    assert scheduler.backlog_batch_size == 9

    default_scheduler = NewsIngestScheduler(session_factory=fake_session_factory, sources_loader=list)
    assert default_scheduler.backlog_batch_size == Settings().news_signal_backlog_batch_size


# ---------------------------------------------------------------------------
# 6. P1：http_pool 分阶段超时 + 关停后不静默复活
# ---------------------------------------------------------------------------


@pytest.fixture()
def _restore_http_pool():
    yield
    http_pool.reset_http_pools()


def test_clients_use_staged_httpx_timeout(_restore_http_pool) -> None:
    """标量 timeout 会被 httpx 同时用于 connect/read/write/pool，最坏耗时叠加。"""
    http_pool.reset_http_pools()
    settings = Settings()

    for client in (http_pool.get_llm_client(), http_pool.get_feed_client(), http_pool.get_crawl_client()):
        assert isinstance(client.timeout, httpx.Timeout)
        assert client.timeout.connect == settings.http_connect_timeout_seconds

    assert http_pool.get_llm_client().timeout.read == settings.llm_timeout_seconds
    assert http_pool.get_llm_client().timeout.connect < http_pool.get_llm_client().timeout.read
    # crawl client 的超时不再硬编码 15，而是读配置
    assert http_pool.get_crawl_client().timeout.read == settings.crawl_timeout_seconds


def test_pools_do_not_silently_revive_after_shutdown(_restore_http_pool) -> None:
    http_pool.reset_http_pools()
    client = http_pool.get_llm_client()

    http_pool.shutdown_http_pools()

    assert client.is_closed is True
    assert http_pool.is_shutdown() is True
    for getter in (
        http_pool.get_llm_client,
        http_pool.get_crawl_client,
        http_pool.get_feed_client,
        http_pool.get_feishu_client,
    ):
        with pytest.raises(http_pool.HttpPoolShutdownError):
            getter()

    # reset 之后（仅测试/重启场景）恢复可用
    http_pool.reset_http_pools()
    assert http_pool.get_llm_client().is_closed is False


def test_close_llm_client_keeps_lazy_rebuild_semantics(_restore_http_pool) -> None:
    """历史入口语义不变：close 之后仍可惰性重建（conftest / lifespan 依赖）。"""
    http_pool.reset_http_pools()
    first = http_pool.get_feed_client()
    http_pool.close_llm_client()
    second = http_pool.get_feed_client()
    assert second is not first
    assert second.is_closed is False


# ---------------------------------------------------------------------------
# 7. P2：commit 之后不再触发 N 次 refresh SELECT
# ---------------------------------------------------------------------------


def _seed_news(url_hashes: list[str]) -> list[int]:
    published_at = datetime(2026, 7, 25, 9, 0, tzinfo=UTC)
    with SessionLocal() as session:
        for url_hash in url_hashes:
            session.add(
                NewsItem(
                    source_name="WS6 Timeliness",
                    source_url="https://example.com/ws6",
                    title=f"WS6 headline {url_hash}",
                    summary="WS6 summary",
                    canonical_url=f"https://example.com/{url_hash}",
                    url_hash=url_hash,
                    market="us",
                    language="en",
                    published_at=published_at,
                    fetched_at=published_at,
                    effective_at=published_at,
                    ingest_status="ingested",
                )
            )
        session.commit()
        return list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))


def _cleanup_news(url_hashes: list[str]) -> None:
    with SessionLocal() as session:
        news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
        if news_ids:
            topic_ids = list(
                session.scalars(
                    select(TopicNewsLink.topic_cluster_id).where(TopicNewsLink.news_id.in_(news_ids))
                )
            )
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(news_ids)))
            session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
            if topic_ids:
                session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
        session.commit()


def test_queue_worker_does_not_refresh_orm_items_after_commit(monkeypatch) -> None:
    """commit 后（expire_on_commit=True）再访问 item.title/... 会每条一次 SELECT。"""
    url_hashes = [f"ws6-refresh-{i}" for i in range(5)]
    _cleanup_news(url_hashes)
    news_ids = _seed_news(url_hashes)
    assert len(news_ids) == 5

    class FakePipelineService:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session

        def process_news_ids(self, ids):
            return pipeline_module.ProcessNewsSignalsSummary(
                news_ids=list(ids), processed_count=len(ids), touched_topic_ids=[]
            )

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            return []

    class NoopBus:
        def publish(self, *args, **kwargs):
            return None

        def publish_batch(self, *args, **kwargs):
            return 0

    class NoopNotifications:
        def on_news_created_batch(self, payloads):
            return None

    monkeypatch.setattr(queue_worker_module, "NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr(queue_worker_module, "get_event_bus", lambda: NoopBus())
    monkeypatch.setattr(queue_worker_module, "get_notification_service", lambda: NoopNotifications())

    state = {"committed": False}
    selects_after_commit: list[str] = []

    def _after_commit(session) -> None:
        state["committed"] = True

    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        if state["committed"] and statement.lstrip().upper().startswith("SELECT"):
            selects_after_commit.append(statement)

    event.listen(SessionLocal, "after_commit", _after_commit)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    try:
        worker = BackgroundQueueWorker(session_factory=SessionLocal, inflight=InflightLeaseRegistry())
        # 指标回写会自带一次 commit，先把它挪出观测窗口。
        worker._next_error_metrics_flush_at = time.monotonic() + 3600
        analysis_queue.put(news_ids)
        assert worker.do_cycle() == 5
    finally:
        event.remove(SessionLocal, "after_commit", _after_commit)
        event.remove(engine, "after_cursor_execute", _after_cursor_execute)
        _cleanup_news(url_hashes)

    news_item_refreshes = [s for s in selects_after_commit if "news_items" in s]
    assert news_item_refreshes == [], (
        f"commit 之后不应再触发 news_items 的 refresh 查询，实际 {len(news_item_refreshes)} 次"
    )


# ---------------------------------------------------------------------------
# 8. 不变量：LLM / 网络调用不在写事务内
# ---------------------------------------------------------------------------


def test_llm_and_crawl_never_run_inside_a_write_transaction(monkeypatch) -> None:
    """pysqlite 在第一条 DML 前才 BEGIN，写锁一直持有到 COMMIT。

    因此不变量可表述为：任何 `llm` / `crawl` 事件都不能出现在
    "某条 INSERT/UPDATE/DELETE 之后、对应 COMMIT 之前"的区间里。
    """
    url_hashes = [f"ws6-txorder-{i}" for i in range(4)]
    _cleanup_news(url_hashes)
    news_ids = _seed_news(url_hashes)

    timeline: list[str] = []
    timeline_lock = threading.Lock()

    def record(tag: str) -> None:
        with timeline_lock:
            timeline.append(tag)

    def fake_crawl(url: str, timeout: float = 15.0) -> str:
        record("crawl")
        return f"body of {url}"

    class FakeClassifier:
        def __init__(self, session) -> None:
            self.session = session

        def classify(self, *, title, summary, body):
            record("llm")
            return pipeline_module.ClassificationResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                topic_key="ws6-topic",
                keywords=["ws6"],
                summary="ws6",
                classifier_type="rule",
                signal_confidence=0.5,
                topic_title_hint=None,
                topic_summary_hint=None,
                llm_error=None,
                takeaway=None,
            )

    monkeypatch.setattr(pipeline_module, "crawl_and_extract_article", fake_crawl)
    monkeypatch.setattr(pipeline_module, "NewsSignalClassifier", FakeClassifier)

    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
        verb = statement.lstrip().split(" ", 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE"}:
            record("dml")

    def _after_commit(session) -> None:
        record("commit")

    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    event.listen(SessionLocal, "after_commit", _after_commit)
    try:
        with SessionLocal() as session:
            service = NewsSignalPipelineService(session, session_factory=SessionLocal)
            summary = service.process_news_ids(news_ids)
            session.commit()
        assert summary.processed_count == len(news_ids)
    finally:
        event.remove(engine, "after_cursor_execute", _after_cursor_execute)
        event.remove(SessionLocal, "after_commit", _after_commit)
        _cleanup_news(url_hashes)

    assert "llm" in timeline and "crawl" in timeline and "dml" in timeline

    write_tx_open = False
    for tag in timeline:
        if tag == "dml":
            write_tx_open = True
        elif tag == "commit":
            write_tx_open = False
        elif tag in {"llm", "crawl"}:
            assert not write_tx_open, f"{tag} 发生在写事务内部：{timeline}"

    # 阶段 1 的正文落库改成批量提交：4 条正文不再是 4 个独立写事务。
    first_llm = timeline.index("llm")
    stage1_commits = [i for i, tag in enumerate(timeline[:first_llm]) if tag == "commit"]
    assert len(stage1_commits) <= 1, f"阶段 1 应当只提交一次，实际 {len(stage1_commits)} 次：{timeline}"
