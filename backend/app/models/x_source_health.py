from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XSourceHealth(Base):
    __tablename__ = "x_source_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    consecutive_failures: Mapped[int] = mapped_column(Integer(), default=0)
    total_fetches: Mapped[int] = mapped_column(Integer(), default=0)
    total_failures: Mapped[int] = mapped_column(Integer(), default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float(), default=None)
    last_error: Mapped[str | None] = mapped_column(Text(), default=None)
