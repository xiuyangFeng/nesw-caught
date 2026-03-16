from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NewsStockMention(TimestampMixin, Base):
    __tablename__ = "news_stock_mention"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    mention_type: Mapped[str] = mapped_column(String(16), default="body")
    confidence: Mapped[float] = mapped_column(Float(), default=0.0)
