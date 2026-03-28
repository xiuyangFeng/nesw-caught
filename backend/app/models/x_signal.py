from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XSignal(Base):
    __tablename__ = "x_signal"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text())
    market: Mapped[str] = mapped_column(String(16), default="us", index=True)
    topic_tag: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    macro_tag: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    primary_symbol: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    priority_score: Mapped[float] = mapped_column(Float(), default=0.0, index=True)
    confidence_score: Mapped[float] = mapped_column(Float(), default=0.0)
    source_count: Mapped[int] = mapped_column(default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
