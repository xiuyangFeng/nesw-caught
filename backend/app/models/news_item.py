from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text, event, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NewsItem(TimestampMixin, Base):
    __tablename__ = "news_item"
    __table_args__ = (
        Index("ix_news_published_id", "published_at", "id"),
        Index("ix_news_market_published_id", "market", "published_at", "id"),
        Index("ix_news_effective_id", "effective_at", "id"),
        Index("ix_news_market_effective_id", "market", "effective_at", "id"),
        # 信号流水线 pending 队列（signal_status IS NULL）的局部索引：只覆盖待处理行，
        # 避免 list_pending_news_ids 全表扫描，同时不为已处理行付写入代价。
        Index("ix_news_pending", "id", sqlite_where=text("signal_status IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text(), default=None)
    ai_takeaway: Mapped[str | None] = mapped_column(Text(), default=None)
    canonical_url: Mapped[str] = mapped_column(String(500), unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(16))
    language: Mapped[str | None] = mapped_column(String(16), default=None)
    sentiment_label: Mapped[str | None] = mapped_column(String(16), default=None)
    sentiment_score: Mapped[float | None] = mapped_column(Float(), default=None)
    signal_status: Mapped[str | None] = mapped_column(String(32), default=None)
    signal_error: Mapped[str | None] = mapped_column(Text(), default=None)
    signal_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingest_status: Mapped[str] = mapped_column(String(32), default="ingested")


def _sync_effective_at(target: NewsItem) -> None:
    target.effective_at = target.published_at or target.fetched_at


@event.listens_for(NewsItem, "before_insert")
def _news_item_before_insert(_mapper, _connection, target: NewsItem) -> None:
    _sync_effective_at(target)


@event.listens_for(NewsItem, "before_update")
def _news_item_before_update(_mapper, _connection, target: NewsItem) -> None:
    _sync_effective_at(target)
