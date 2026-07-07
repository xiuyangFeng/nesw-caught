from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = (UniqueConstraint("source_name", "market", name="uq_source_health_source_market"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    consecutive_failures: Mapped[int] = mapped_column(Integer(), default=0)
    total_fetches: Mapped[int] = mapped_column(Integer(), default=0)
    total_failures: Mapped[int] = mapped_column(Integer(), default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float(), default=None)
    is_disabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    last_etag: Mapped[str | None] = mapped_column(String(256), default=None)
    last_modified: Mapped[str | None] = mapped_column(String(128), default=None)

