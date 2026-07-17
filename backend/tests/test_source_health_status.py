from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.source_health import SourceHealth
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.persister import ItemPersister
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome, SourceFetchResult
from app.services.news_ingest_scheduler import NewsIngestScheduler
from app.services.news_ingestion import RefreshSummary


def _source(name: str = "probe") -> SourceDefinition:
    return SourceDefinition(
        name=name,
        source_type="rss",
        url="https://example.com/rss",
        market="us",
        cadence_seconds=300,
    )


def test_persist_empty_http_200_marks_empty_not_ok() -> None:
    source = _source("empty-source")
    with SessionLocal() as session:
        persister = ItemPersister(session, SourceHealthRepository(session))
        result = persister.persist_outcome(
            SourceFetchOutcome(
                source=source,
                items=[],
                error=None,
                latency_ms=12.0,
                http_status=200,
                is_not_modified=False,
            )
        )
        assert result.status == "empty"
        health = session.scalars(select(SourceHealth).where(SourceHealth.source_name == source.name)).one()
        assert health.last_status == "empty"
        assert health.consecutive_empty_batches >= 1
        assert health.consecutive_failures == 0
        assert health.last_http_status == 200
        assert health.last_fetched_count == 0


def test_record_failure_clears_empty_batch_streak() -> None:
    source = _source("hard-fail-source")
    with SessionLocal() as session:
        repo = SourceHealthRepository(session)
        health = repo.get_or_create(source_name=source.name, source_type="rss", market="us")
        health.consecutive_empty_batches = 4
        session.commit()

        persister = ItemPersister(session, repo)
        result = persister.record_failure(
            source,
            error="timeout",
            latency_ms=9.0,
            status="http_error",
            http_status=503,
        )
        assert result.status == "http_error"
        session.refresh(health)
        assert health.consecutive_empty_batches == 0
        assert health.last_status == "http_error"
        assert health.consecutive_failures >= 1


def test_persist_not_modified_clears_failure_and_records_status() -> None:
    source = _source("nm-source")
    with SessionLocal() as session:
        repo = SourceHealthRepository(session)
        health = repo.get_or_create(source_name=source.name, source_type="rss", market="us")
        health.consecutive_failures = 3
        health.consecutive_empty_batches = 2
        session.commit()

        persister = ItemPersister(session, repo)
        result = persister.persist_outcome(
            SourceFetchOutcome(
                source=source,
                items=[],
                error=None,
                latency_ms=5.0,
                http_status=304,
                is_not_modified=True,
            )
        )
        assert result.status == "not_modified"
        session.refresh(health)
        assert health.last_status == "not_modified"
        assert health.consecutive_failures == 0
        assert health.consecutive_empty_batches == 0
        assert health.last_http_status == 304


def test_scheduler_does_not_backoff_on_not_modified_or_empty_below_threshold(monkeypatch) -> None:
    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0

        def __call__(self) -> float:
            return self.now

    @contextmanager
    def session_factory():
        yield object()

    source = _source("soft")

    class FakeIngestion:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self, sources=None):
            now = datetime.now(UTC)
            return RefreshSummary(
                started_at=now,
                finished_at=now,
                fetched_count=0,
                inserted_count=0,
                results=[
                    SourceFetchResult(
                        source_name=source.name,
                        source_type="rss",
                        status="not_modified",
                        fetched_count=0,
                        inserted_count=0,
                        error=None,
                        latency_ms=1.0,
                    )
                ],
            )

    class FakePipeline:
        def __init__(self, session) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            return []

        def process_news_ids(self, news_ids: list[int]):
            return None

    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsIngestionService", FakeIngestion)
    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsSignalPipelineService", FakePipeline)

    clock = FakeClock()
    scheduler = NewsIngestScheduler(
        session_factory=session_factory,
        sources_loader=lambda: [source],
        clock=clock,
    )
    monkeypatch.setattr(scheduler, "_record_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "_record_failure", lambda *args, **kwargs: None)

    assert scheduler.run_cycle() == 0
    assert scheduler._failure_streak.get(source.name, 0) == 0
    assert scheduler.backoff_delay_seconds(source) == 300.0


def test_scheduler_applies_empty_circuit_probe_after_threshold(monkeypatch) -> None:
    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0

        def __call__(self) -> float:
            return self.now

    @contextmanager
    def session_factory():
        yield object()

    source = _source("empty-soft")
    calls = {"n": 0}

    class FakeIngestion:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self, sources=None):
            calls["n"] += 1
            now = datetime.now(UTC)
            return RefreshSummary(
                started_at=now,
                finished_at=now,
                fetched_count=0,
                inserted_count=0,
                results=[
                    SourceFetchResult(
                        source_name=source.name,
                        source_type="rss",
                        status="empty",
                        fetched_count=0,
                        inserted_count=0,
                        error="parsed 0 items",
                        latency_ms=1.0,
                    )
                ],
            )

    class FakePipeline:
        def __init__(self, session) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
            return []

        def process_news_ids(self, news_ids: list[int]):
            return None

    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsIngestionService", FakeIngestion)
    monkeypatch.setattr("app.services.news_ingest_scheduler.NewsSignalPipelineService", FakePipeline)

    clock = FakeClock()
    scheduler = NewsIngestScheduler(
        session_factory=session_factory,
        sources_loader=lambda: [source],
        clock=clock,
        empty_circuit_threshold=3,
    )
    monkeypatch.setattr(scheduler, "_record_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "_record_failure", lambda *args, **kwargs: None)

    for _ in range(3):
        scheduler.run_cycle()
        # force due again for next empty observation
        scheduler._next_due_at[source.name] = 0.0

    assert scheduler._empty_streak[source.name] == 3
    assert scheduler._failure_streak.get(source.name, 0) == 0
    assert scheduler.backoff_delay_seconds(source) == 600.0
