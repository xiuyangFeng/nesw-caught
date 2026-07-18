from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

from app.services.news_ingest_scheduler import NewsIngestScheduler
from app.services.news_ingestion import RefreshSummary, SourceDefinition, SourceFetchResult


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

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


def _sources() -> list[SourceDefinition]:
    return [
        SourceDefinition(name="fast", source_type="rss", url="https://a.example/rss", market="us", cadence_seconds=300),
        SourceDefinition(name="flaky", source_type="rss", url="https://b.example/rss", market="us", cadence_seconds=300),
    ]


def _result(name: str, *, ok: bool) -> SourceFetchResult:
    return SourceFetchResult(
        source_name=name,
        source_type="rss",
        status="ok" if ok else "error",
        fetched_count=1 if ok else 0,
        inserted_count=1 if ok else 0,
        error=None if ok else "boom",
        latency_ms=1.0,
    )


def _summary(results: list[SourceFetchResult]) -> RefreshSummary:
    now = datetime.now(UTC)
    inserted_count = sum(r.inserted_count for r in results)
    fetched_count = sum(r.fetched_count for r in results)
    return RefreshSummary(
        started_at=now,
        finished_at=now,
        fetched_count=fetched_count,
        inserted_count=inserted_count,
        results=results,
    )


def _build_scheduler(monkeypatch, *, flaky_fails: bool) -> tuple[NewsIngestScheduler, FakeClock]:
    class FakeIngestionService:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self, sources=None):
            return _summary(
                [_result(source.name, ok=(source.name != "flaky" or not flaky_fails)) for source in (sources or [])]
            )

    class FakePipelineService:
        def __init__(self, session) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            return []

        def process_news_ids(self, news_ids: list[int]):
            return None

    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsIngestionService", FakeIngestionService)
    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsSignalPipelineService", FakePipelineService)

    clock = FakeClock()
    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=_sources,
        clock=clock,
    )
    # 测试不关心 runtime status 落库
    monkeypatch.setattr(scheduler, "_record_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "_record_failure", lambda *args, **kwargs: None)
    return scheduler, clock


def test_scheduler_respects_cadence(monkeypatch) -> None:
    scheduler, clock = _build_scheduler(monkeypatch, flaky_fails=False)

    assert scheduler.run_cycle() == 2  # 首轮全部到期
    assert scheduler.run_cycle() == 0  # cadence 内不重复抓取

    clock.advance(299)
    assert scheduler.run_cycle() == 0
    clock.advance(2)
    assert scheduler.run_cycle() == 2  # cadence 到期后再次全量


def test_scheduler_applies_exponential_backoff_on_failure(monkeypatch) -> None:
    scheduler, clock = _build_scheduler(monkeypatch, flaky_fails=True)

    assert scheduler.run_cycle() == 1
    # fast 成功:300s 后到期;flaky 失败 1 次:300*2=600s 后到期
    clock.advance(301)
    assert [source.name for source in scheduler.due_sources()] == ["fast"]
    assert scheduler.run_cycle() == 1

    clock.advance(300)  # t=601: flaky 到期(600s)且 fast 到期
    due_names = {source.name for source in scheduler.due_sources()}
    assert due_names == {"fast", "flaky"}
    assert scheduler.run_cycle() == 1

    # flaky 失败 2 次 → 300*4=1200s
    flaky = _sources()[1]
    assert scheduler.backoff_delay_seconds(flaky) == 1200.0


def test_scheduler_backoff_is_capped(monkeypatch) -> None:
    scheduler, _clock = _build_scheduler(monkeypatch, flaky_fails=True)
    flaky = _sources()[1]
    scheduler._failure_streak["flaky"] = 10
    assert scheduler.backoff_delay_seconds(flaky) == 300.0 * 8  # multiplier 上限 8


def test_scheduler_drains_signal_backlog(monkeypatch) -> None:
    from app.workers.queue_worker import analysis_queue

    while not analysis_queue.empty():
        analysis_queue.get_nowait()

    processed: list[list[int]] = []

    class FakePipelineService:
        def __init__(self, session) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            return [1, 2, 3]

        def process_news_ids(self, news_ids: list[int]):
            processed.append(list(news_ids))
            return None

    class FakeIngestionService:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self, sources=None):
            return _summary([])

    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsIngestionService", FakeIngestionService)
    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsSignalPipelineService", FakePipelineService)

    clock = FakeClock()
    scheduler = NewsIngestScheduler(
        session_factory=fake_session_factory,
        sources_loader=list,  # 无源
        clock=clock,
    )
    monkeypatch.setattr(scheduler, "_record_success", lambda **kwargs: None)

    scheduler.run_cycle()
    # drain 不再就地处理(避免与 queue_worker 并行重复消费),而是投入分析队列
    assert processed == []
    assert analysis_queue.get_nowait() == [1, 2, 3]
