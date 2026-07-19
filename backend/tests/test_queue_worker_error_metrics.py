"""Tests for the suppressed-exception observability metrics added per
optimization-plan.md #12: pipeline/event_bus/llm_providers swallow single-item
failures (existing "one failure doesn't break the batch" semantics is
preserved), but the counts must now be periodically exposed via the existing
`worker_runtime_status` table instead of only appearing in logs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.services import event_bus as event_bus_module
from app.services import llm_providers, news_signal_pipeline
from app.workers import queue_worker as queue_worker_module
from app.workers.queue_worker import BackgroundQueueWorker


@pytest.fixture()
def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_maybe_flush_error_metrics_writes_deltas_to_worker_runtime_status(
    _session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = BackgroundQueueWorker(session_factory=_session_factory)

    # Simulate a swallowed crawl failure and a swallowed notification-enqueue
    # failure (both already logged elsewhere; here we only assert they are
    # reflected as counted, observable metrics).
    news_signal_pipeline._incr_pipeline_error("crawl_error")
    queue_worker_module._incr_notification_error()
    llm_providers._incr_llm_error("token_usage_log_failed")

    local_bus = event_bus_module.InMemoryEventBus()
    local_bus.handler_error_count = 2
    fake_bus = event_bus_module.HybridEventBus(backend="memory", local_bus=local_bus)
    monkeypatch.setattr(queue_worker_module, "get_event_bus", lambda: fake_bus)

    worker._maybe_flush_error_metrics()

    with _session_factory() as session:
        rows = {
            row.worker_name: row
            for row in session.scalars(
                select(WorkerRuntimeStatus).where(
                    WorkerRuntimeStatus.worker_name.like(f"{worker.worker_name}:%")
                )
            )
        }

    assert f"{worker.worker_name}:crawl_error" in rows
    assert f"{worker.worker_name}:notification_error" in rows
    assert f"{worker.worker_name}:llm_token_usage_log_failed" in rows
    assert f"{worker.worker_name}:event_handler_error" in rows
    for row in rows.values():
        assert row.status == "degraded"
        assert row.failure_count == 1
        assert "suppressed exception" in row.last_error


def test_maybe_flush_error_metrics_is_throttled_and_never_raises(
    _session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second call within the flush interval must be a no-op (avoids write
    amplification), and a broken event bus must not crash the worker cycle
    (single-flush failure isolation, matching BaseWorker's own contract)."""
    worker = BackgroundQueueWorker(session_factory=_session_factory)

    # Pin a known-good, real event bus for the first two flushes rather than
    # relying on the ambient process-wide singleton (other test modules are
    # known to leave `app.services.event_bus`'s global `_instance` pointed at
    # a bare test double after they run, which is an unrelated pre-existing
    # isolation gap in those tests — irrelevant to what this test verifies).
    working_bus = event_bus_module.HybridEventBus(backend="memory", local_bus=event_bus_module.InMemoryEventBus())
    monkeypatch.setattr(queue_worker_module, "get_event_bus", lambda: working_bus)

    news_signal_pipeline._incr_pipeline_error("crawl_error")
    worker._maybe_flush_error_metrics()

    with _session_factory() as session:
        count_after_first = session.scalar(
            select(WorkerRuntimeStatus).where(
                WorkerRuntimeStatus.worker_name == f"{worker.worker_name}:crawl_error"
            )
        ).failure_count

    news_signal_pipeline._incr_pipeline_error("crawl_error")
    worker._maybe_flush_error_metrics()  # still within throttle window: no-op

    with _session_factory() as session:
        count_after_second = session.scalar(
            select(WorkerRuntimeStatus).where(
                WorkerRuntimeStatus.worker_name == f"{worker.worker_name}:crawl_error"
            )
        ).failure_count

    assert count_after_second == count_after_first

    # Force past the throttle window and break the event bus lookup entirely;
    # the flush must swallow the error rather than propagate it.
    worker._next_error_metrics_flush_at = 0.0

    def _boom():
        raise RuntimeError("event bus unavailable")

    monkeypatch.setattr(queue_worker_module, "get_event_bus", _boom)

    worker._maybe_flush_error_metrics()  # must not raise
