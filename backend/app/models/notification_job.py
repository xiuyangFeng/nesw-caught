from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NotificationJob(TimestampMixin, Base):
    __tablename__ = "notification_job"
    __table_args__ = (
        # 并发入队去重的唯一约束：只覆盖非空 dedupe_key（SQLite partial
        # index），避免"先查后插"窗口内并发请求各自查不到而重复插入同一
        # 逻辑事件；dedupe_key 为 NULL 的弱去重行不受影响，允许多条并存。
        # 取代原先的普通单列索引（ix_notification_job_dedupe_key），避免
        # 同列上重复建两份索引造成写放大。
        Index(
            "ux_notification_job_dedupe_key",
            "dedupe_key",
            unique=True,
            sqlite_where=text("dedupe_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), default=None)
    last_error: Mapped[str | None] = mapped_column(Text(), default=None)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
