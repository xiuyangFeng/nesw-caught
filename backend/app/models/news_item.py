from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NewsItem(TimestampMixin, Base):
    __tablename__ = "news_item"
    __table_args__ = (
        Index("ix_news_published_id", "published_at", "id"),
        Index("ix_news_market_published_id", "market", "published_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500), index=True)
    summary: Mapped[str | None] = mapped_column(Text(), default=None)
    canonical_url: Mapped[str] = mapped_column(String(500), unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    language: Mapped[str | None] = mapped_column(String(16), default=None)
    sentiment_label: Mapped[str | None] = mapped_column(String(16), default=None)
    sentiment_score: Mapped[float | None] = mapped_column(Float(), default=None)
    signal_status: Mapped[str | None] = mapped_column(String(32), default=None)
    signal_error: Mapped[str | None] = mapped_column(Text(), default=None)
    signal_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingest_status: Mapped[str] = mapped_column(String(32), default="ingested")
