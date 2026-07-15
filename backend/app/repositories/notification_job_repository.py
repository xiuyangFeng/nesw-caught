from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.models.notification_job import NotificationJob


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_job(job: NotificationJob) -> NotificationJob:
    job.created_at = _ensure_utc(job.created_at)  # type: ignore[assignment]
    job.next_retry_at = _ensure_utc(job.next_retry_at)  # type: ignore[assignment]
    job.lease_until = _ensure_utc(job.lease_until)  # type: ignore[assignment]
    job.sent_at = _ensure_utc(job.sent_at)  # type: ignore[assignment]
    return job


class NotificationJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, job_id: int) -> NotificationJob | None:
        stmt = select(NotificationJob).where(NotificationJob.id == job_id)
        job = self.session.scalar(stmt)
        if job is None:
            return None
        self.session.expunge(job)
        return _normalize_job(job)

    def get_by_dedupe_key(self, dedupe_key: str) -> NotificationJob | None:
        stmt = select(NotificationJob).where(NotificationJob.dedupe_key == dedupe_key).limit(1)
        job = self.session.scalar(stmt)
        if job is None:
            return None
        self.session.expunge(job)
        return _normalize_job(job)

    def enqueue(
        self,
        *,
        channel: str,
        event_type: str,
        payload: dict[str, Any],
        dedupe_key: str | None = None,
        next_retry_at: datetime | None = None,
    ) -> NotificationJob:
        normalized_dedupe_key = dedupe_key.strip() if dedupe_key else None
        if normalized_dedupe_key:
            existing = self.get_by_dedupe_key(normalized_dedupe_key)
            if existing is not None:
                return existing

        job = NotificationJob(
            channel=channel,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="pending",
            attempt_count=0,
            next_retry_at=_ensure_utc(next_retry_at),
            dedupe_key=normalized_dedupe_key,
        )
        self.session.add(job)
        self.session.flush()
        self.session.refresh(job)
        return _normalize_job(job)

    def enqueue_source_event(
        self,
        *,
        payload: dict[str, Any],
        dedupe_key: str | None = None,
        channel: str = "news",
    ) -> NotificationJob:
        return self.enqueue(
            channel=channel,
            event_type="news_source_event",
            payload=payload,
            dedupe_key=dedupe_key,
        )

    def list_pending(
        self,
        *,
        channel: str | None = None,
        event_type: str | None = None,
        now: datetime | None = None,
        limit: int = 50,
    ) -> list[NotificationJob]:
        now = _ensure_utc(now) or _utc_now()
        conditions = [
            NotificationJob.status == "pending",
            or_(NotificationJob.next_retry_at.is_(None), NotificationJob.next_retry_at <= now),
        ]
        if channel:
            conditions.append(NotificationJob.channel == channel)
        if event_type:
            conditions.append(NotificationJob.event_type == event_type)

        stmt = (
            select(NotificationJob)
            .where(and_(*conditions))
            .order_by(
                NotificationJob.next_retry_at.is_(None).desc(),
                NotificationJob.next_retry_at.asc(),
                NotificationJob.created_at.asc(),
                NotificationJob.id.asc(),
            )
            .limit(limit)
        )
        jobs = list(self.session.scalars(stmt))
        for job in jobs:
            self.session.expunge(job)
        return [_normalize_job(job) for job in jobs]

    def claim_next_ready(
        self,
        *,
        channel: str | None = None,
        event_type: str | None = None,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> NotificationJob | None:
        self.reclaim_expired_sending_leases(channel=channel, event_type=event_type, now=now)
        current_time = _ensure_utc(now) or _utc_now()
        lease_until = current_time + timedelta(seconds=lease_seconds)
        for candidate in self.list_pending(channel=channel, event_type=event_type, now=now, limit=10):
            lease_token = uuid4().hex
            result = self.session.execute(
                update(NotificationJob)
                .where(NotificationJob.id == candidate.id, NotificationJob.status == "pending")
                .values(
                    status="sending",
                    attempt_count=NotificationJob.attempt_count + 1,
                    lease_until=lease_until,
                    lease_token=lease_token,
                )
            )
            self.session.flush()
            if result.rowcount:
                claimed = self.get_by_id(candidate.id)
                if claimed is not None:
                    return claimed
        return None

    def reclaim_expired_sending_leases(
        self,
        *,
        channel: str | None = None,
        event_type: str | None = None,
        now: datetime | None = None,
        limit: int = 50,
    ) -> list[NotificationJob]:
        current_time = _ensure_utc(now) or _utc_now()
        conditions = [
            NotificationJob.status == "sending",
            NotificationJob.lease_until.is_not(None),
            NotificationJob.lease_until <= current_time,
        ]
        if channel:
            conditions.append(NotificationJob.channel == channel)
        if event_type:
            conditions.append(NotificationJob.event_type == event_type)

        stmt = (
            select(NotificationJob)
            .where(and_(*conditions))
            .order_by(NotificationJob.lease_until.asc(), NotificationJob.id.asc())
            .limit(limit)
        )
        jobs = list(self.session.scalars(stmt))
        if not jobs:
            return []

        for job in jobs:
            job.status = "pending"
            job.lease_until = None
            job.lease_token = None
            self.session.add(job)

        self.session.flush()
        for job in jobs:
            self.session.refresh(job)
        return [_normalize_job(job) for job in jobs]

    def mark_sent(
        self,
        job_id: int,
        *,
        sent_at: datetime | None = None,
        lease_token: str | None = None,
    ) -> NotificationJob:
        return self._finalize(
            job_id,
            values={
                "status": "sent",
                "sent_at": _ensure_utc(sent_at) or _utc_now(),
                "lease_until": None,
                "lease_token": None,
                "last_error": None,
            },
            lease_token=lease_token,
        )

    def mark_retryable_failure(
        self,
        job_id: int,
        *,
        error: str,
        next_retry_at: datetime,
        lease_token: str | None = None,
    ) -> NotificationJob:
        return self._finalize(
            job_id,
            values={
                "status": "pending",
                "last_error": error,
                "next_retry_at": _ensure_utc(next_retry_at),
                "lease_until": None,
                "lease_token": None,
            },
            lease_token=lease_token,
        )

    def mark_failed(
        self,
        job_id: int,
        *,
        error: str,
        lease_token: str | None = None,
    ) -> NotificationJob:
        return self._finalize(
            job_id,
            values={
                "status": "failed",
                "last_error": error,
                "lease_until": None,
                "lease_token": None,
            },
            lease_token=lease_token,
        )

    def discard_pending(
        self,
        *,
        channel: str | None = None,
        event_type: str | None = None,
    ) -> int:
        conditions = [NotificationJob.status == "pending"]
        if channel:
            conditions.append(NotificationJob.channel == channel)
        if event_type:
            conditions.append(NotificationJob.event_type == event_type)
        result = self.session.execute(delete(NotificationJob).where(and_(*conditions)))
        self.session.flush()
        return int(result.rowcount or 0)

    def _require(self, job_id: int) -> NotificationJob:
        job = self.get_by_id(job_id)
        if job is None:
            raise ValueError(f"notification job {job_id} not found")
        return job

    def _finalize(
        self,
        job_id: int,
        *,
        values: dict[str, Any],
        lease_token: str | None,
    ) -> NotificationJob:
        conditions = [NotificationJob.id == job_id]
        if lease_token is not None:
            conditions.extend([
                NotificationJob.status == "sending",
                NotificationJob.lease_token == lease_token,
            ])
        result = self.session.execute(update(NotificationJob).where(and_(*conditions)).values(**values))
        self.session.flush()
        if not result.rowcount:
            return self._require(job_id)
        return self._require(job_id)
