from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text

from app.db.session import SessionLocal, engine
from app.models.notification_job import NotificationJob
from app.repositories.notification_job_repository import NotificationJobRepository


def _cleanup_notification_jobs() -> None:
    inspector = inspect(engine)
    if "notification_job" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM notification_job"))


def test_initialize_database_creates_notification_job_table() -> None:
    inspector = inspect(engine)
    assert "notification_job" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("notification_job")}
    assert {
        "id",
        "channel",
        "event_type",
        "payload_json",
        "status",
        "attempt_count",
        "next_retry_at",
        "dedupe_key",
        "last_error",
        "lease_until",
        "lease_token",
        "created_at",
        "sent_at",
    }.issubset(columns)


def test_notification_job_repository_enqueues_source_events_with_weak_dedupe() -> None:
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)

        job = repo.enqueue_source_event(
            payload={"source_name": "Reuters", "news_ids": [1, 2, 3]},
            dedupe_key="source:reuters:2026-03-28T10:00:00Z",
        )
        duplicate = repo.enqueue_source_event(
            payload={"source_name": "Reuters", "news_ids": [1, 2, 3], "duplicate": True},
            dedupe_key="source:reuters:2026-03-28T10:00:00Z",
        )

        assert duplicate.id == job.id
        assert duplicate.channel == "news"
        assert duplicate.event_type == "news_source_event"
        assert duplicate.status == "pending"
        assert duplicate.attempt_count == 0
        assert json.loads(duplicate.payload_json) == {"source_name": "Reuters", "news_ids": [1, 2, 3]}
        assert duplicate.created_at.tzinfo is not None

        stored = session.get(NotificationJob, job.id)
        assert stored is not None
        assert stored.dedupe_key == "source:reuters:2026-03-28T10:00:00Z"


def test_notification_job_repository_claims_retries_and_marks_sent() -> None:
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        repo.enqueue_source_event(payload={"source_name": "Reuters", "news_ids": [11]})

        claimed = repo.claim_next_ready(lease_seconds=120)
        assert claimed is not None
        assert claimed.status == "sending"
        assert claimed.attempt_count == 1
        assert claimed.lease_until is not None
        assert claimed.lease_until > datetime.now(timezone.utc)

        retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        retried = repo.mark_retryable_failure(
            claimed.id,
            error="temporary network error",
            next_retry_at=retry_at,
        )
        assert retried.status == "pending"
        assert retried.attempt_count == 1
        assert retried.last_error == "temporary network error"
        assert retried.next_retry_at == retry_at
        assert retried.lease_until is None

        assert repo.claim_next_ready(now=retry_at - timedelta(seconds=1)) is None

        claimed_again = repo.claim_next_ready(now=retry_at + timedelta(seconds=1))
        assert claimed_again is not None
        assert claimed_again.id == claimed.id
        assert claimed_again.attempt_count == 2

        sent = repo.mark_sent(claimed_again.id)
        assert sent.status == "sent"
        assert sent.sent_at is not None
        assert sent.lease_until is None
        assert sent.last_error is None


def test_notification_job_repository_reclaims_expired_sending_leases() -> None:
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        job = repo.enqueue(
            channel="feishu",
            event_type="analysis_result",
            payload={"news_id": 42},
        )

        claimed = repo.claim_next_ready(lease_seconds=1)
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == "sending"

        # repository 只 flush：先提交释放写事务，下面才能用独立连接改写租约。
        session.commit()

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE notification_job SET lease_until = :lease_until WHERE id = :id"),
                {
                    "lease_until": datetime.now(timezone.utc) - timedelta(seconds=1),
                    "id": claimed.id,
                },
            )

        reclaimed = repo.reclaim_expired_sending_leases()
        assert len(reclaimed) == 1
        assert reclaimed[0].id == claimed.id
        assert reclaimed[0].status == "pending"
        assert reclaimed[0].lease_until is None

        claimed_after_restart = repo.claim_next_ready()
        assert claimed_after_restart is not None
        assert claimed_after_restart.id == claimed.id
        assert claimed_after_restart.attempt_count == 2


def test_notification_job_repository_marks_terminal_failure() -> None:
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        job = repo.enqueue(
            channel="feishu",
            event_type="watchlist_alert",
            payload={"symbol": "AAPL"},
        )

        claimed = repo.claim_next_ready()
        assert claimed is not None
        assert claimed.id == job.id

        failed = repo.mark_failed(claimed.id, error="permanent config error")
        assert failed.status == "failed"
        assert failed.last_error == "permanent config error"
        assert failed.sent_at is None
        assert failed.lease_until is None


def test_notification_job_repository_requires_matching_lease_token_for_finalize() -> None:
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        repo.enqueue(channel="feishu", event_type="analysis_result", payload={"news_id": 42})

        claimed = repo.claim_next_ready()
        assert claimed is not None
        assert claimed.lease_token is not None

        unchanged = repo.mark_sent(claimed.id, lease_token="wrong-token")
        assert unchanged.status == "sending"

        sent = repo.mark_sent(claimed.id, lease_token=claimed.lease_token)
        assert sent.status == "sent"
