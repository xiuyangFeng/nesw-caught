from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicNewsLink(Base):
    __tablename__ = "topic_news_link"
    # 覆盖索引：batch_news_for_topics 按 topic_cluster_id 过滤后立刻要 news_id 去 join。
    # 此前只有两个单列索引，命中 topic_cluster_id 后每行都要回表取 news_id。
    __table_args__ = (Index("ix_topic_news_link_topic_news", "topic_cluster_id", "news_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_cluster_id: Mapped[int] = mapped_column(ForeignKey("topic_cluster.id", ondelete="CASCADE"), index=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), index=True)
