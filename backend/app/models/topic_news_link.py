from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicNewsLink(Base):
    __tablename__ = "topic_news_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_cluster_id: Mapped[int] = mapped_column(ForeignKey("topic_cluster.id", ondelete="CASCADE"), index=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), index=True)
