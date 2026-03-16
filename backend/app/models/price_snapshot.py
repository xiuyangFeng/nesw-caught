from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    price: Mapped[float] = mapped_column(Float())
    change_amount: Mapped[float | None] = mapped_column(Float(), default=None)
    change_percent: Mapped[float | None] = mapped_column(Float(), default=None)
    volume: Mapped[int | None] = mapped_column(Integer(), default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
