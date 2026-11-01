from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Alert(TimestampMixin, Base):
    """站内提醒（聚焦改造 P2）。

    - ``dedupe_key`` 唯一：价格 ``price:{symbol}:{交易日}``、新闻 ``news:{news_id}:{symbol}``、
      合并 ``watch_digest:{窗口起点}``，跨进程重启保持"每股每天一次"等去重语义。
    - ``visible_at``：静默时段产生的提醒延后到次日早上才可见（``overnight=True``）。
    """

    __tablename__ = "alert"
    __table_args__ = (Index("ix_alert_visible_at", "visible_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text(), default="")
    payload_json: Mapped[str] = mapped_column(Text(), default="{}")
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    overnight: Mapped[bool] = mapped_column(Boolean(), default=False)
    visible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
