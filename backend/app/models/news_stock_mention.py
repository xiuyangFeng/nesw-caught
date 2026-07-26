from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NewsStockMention(TimestampMixin, Base):
    __tablename__ = "news_stock_mention"
    # 覆盖索引：portfolio / research / kline / related-news 都走
    # “按 symbol 找 news_id 再 join news_item”。此前命中 symbol 后要逐行回表取 news_id。
    __table_args__ = (Index("ix_news_stock_mention_symbol_news", "symbol", "news_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    mention_type: Mapped[str] = mapped_column(String(16), default="body")
    confidence: Mapped[float] = mapped_column(Float(), default=0.0)
