from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SignalEvent(Base):
    __tablename__ = "signal_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_level: Mapped[str] = mapped_column(String(16), default="info")
    related_symbol: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    related_topic_id: Mapped[int | None] = mapped_column(default=None, index=True)
    reason: Mapped[str | None] = mapped_column(Text(), default=None)
    payload_json: Mapped[str | None] = mapped_column(Text(), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
