from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.worker_runtime_status import WorkerRuntimeStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkerRuntimeStatusRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_name(self, worker_name: str) -> WorkerRuntimeStatus | None:
        stmt = select(WorkerRuntimeStatus).where(WorkerRuntimeStatus.worker_name == worker_name)
        return self.session.scalar(stmt)

    def record_success(self, *, worker_name: str, quotes_count: int) -> WorkerRuntimeStatus:
        status = self._get_or_create(worker_name)
        now = _utc_now()
        status.status = "ok"
        status.last_heartbeat_at = now
        status.last_success_at = now
        status.last_error = None
        status.cycle_count += 1
        status.success_count += 1
        status.last_quotes_count = quotes_count
        self.session.add(status)
        self.session.commit()
        self.session.refresh(status)
        return status

    def record_failure(self, *, worker_name: str, error: str) -> WorkerRuntimeStatus:
        status = self._get_or_create(worker_name)
        now = _utc_now()
        status.status = "degraded"
        status.last_heartbeat_at = now
        status.last_failure_at = now
        status.last_error = error
        status.cycle_count += 1
        status.failure_count += 1
        self.session.add(status)
        self.session.commit()
        self.session.refresh(status)
        return status

    def _get_or_create(self, worker_name: str) -> WorkerRuntimeStatus:
        existing = self.get_by_name(worker_name)
        if existing is not None:
            return existing
        return WorkerRuntimeStatus(
            worker_name=worker_name,
            status="idle",
            cycle_count=0,
            success_count=0,
            failure_count=0,
            last_quotes_count=0,
        )
