from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NotificationJob(TimestampMixin, Base):
    __tablename__ = "notification_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    last_error: Mapped[str | None] = mapped_column(Text(), default=None)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
