from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkerRuntimeStatus(Base):
    __tablename__ = "worker_runtime_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(String(255), default=None)
    cycle_count: Mapped[int] = mapped_column(Integer(), default=0)
    success_count: Mapped[int] = mapped_column(Integer(), default=0)
    failure_count: Mapped[int] = mapped_column(Integer(), default=0)
    last_quotes_count: Mapped[int] = mapped_column(Integer(), default=0)
