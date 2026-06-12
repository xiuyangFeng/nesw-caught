from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArticleContent(Base):
    __tablename__ = "article_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, index=True)
    content_text: Mapped[str | None] = mapped_column(Text(), default=None)
    content_html: Mapped[str | None] = mapped_column(Text(), default=None)
    extract_status: Mapped[str] = mapped_column(default="pending")
    extract_error: Mapped[str | None] = mapped_column(Text(), default=None)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
