from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XPostSymbolMention(Base):
    __tablename__ = "x_post_symbol_mention"

    id: Mapped[int] = mapped_column(primary_key=True)
    x_post_id: Mapped[int] = mapped_column(ForeignKey("x_post.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float(), default=0.0)
