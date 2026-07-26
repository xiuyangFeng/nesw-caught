from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicCluster(Base):
    __tablename__ = "topic_cluster"
    # feed-layout / topics / 事件详情每个请求都要按 (importance_score, last_seen_at)
    # 排序取前若干条，此前只能全量排序。
    __table_args__ = (Index("ix_topic_cluster_importance_seen", "importance_score", "last_seen_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_key: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, default=None)
    topic_title: Mapped[str] = mapped_column(String(255), index=True)
    topic_summary: Mapped[str | None] = mapped_column(Text(), default=None)
    keywords: Mapped[str | None] = mapped_column(Text(), default=None)
    sentiment_score: Mapped[float | None] = mapped_column(Float(), default=None)
    importance_score: Mapped[float | None] = mapped_column(Float(), default=None)
    cluster_version: Mapped[int] = mapped_column(default=1)
    llm_refined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
