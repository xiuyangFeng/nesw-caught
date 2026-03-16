from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicCluster(Base):
    __tablename__ = "topic_cluster"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_title: Mapped[str] = mapped_column(String(255), index=True)
    topic_summary: Mapped[str | None] = mapped_column(Text(), default=None)
    keywords: Mapped[str | None] = mapped_column(Text(), default=None)
    sentiment_score: Mapped[float | None] = mapped_column(Float(), default=None)
    importance_score: Mapped[float | None] = mapped_column(Float(), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
