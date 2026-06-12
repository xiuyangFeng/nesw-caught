from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsSignalResult(Base):
    __tablename__ = "news_signal_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, index=True)
    classifier_type: Mapped[str] = mapped_column(String(32), default="rule")
    signal_confidence: Mapped[float | None] = mapped_column(Float(), default=None)
    topic_key: Mapped[str | None] = mapped_column(String(255), default=None)
    keywords: Mapped[str | None] = mapped_column(Text(), default=None)
    summary: Mapped[str | None] = mapped_column(Text(), default=None)
    payload_json: Mapped[str | None] = mapped_column(Text(), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
