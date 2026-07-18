from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"
    __table_args__ = (
        # (symbol, fetched_at) 复合索引：支撑“每 symbol 最新一条”的 GROUP BY + 回表
        # 以及按 symbol 取历史的回测查询。
        Index("ix_price_snapshot_symbol_fetched", "symbol", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    price: Mapped[float] = mapped_column(Float())
    change_amount: Mapped[float | None] = mapped_column(Float(), default=None)
    change_percent: Mapped[float | None] = mapped_column(Float(), default=None)
    open_price: Mapped[float | None] = mapped_column(Float(), default=None)
    previous_close: Mapped[float | None] = mapped_column(Float(), default=None)
    day_high: Mapped[float | None] = mapped_column(Float(), default=None)
    day_low: Mapped[float | None] = mapped_column(Float(), default=None)
    volume: Mapped[int | None] = mapped_column(Integer(), default=None)
    provider_name: Mapped[str | None] = mapped_column(String(64), default=None)
    provider_symbol: Mapped[str | None] = mapped_column(String(32), default=None)
    quote_status: Mapped[str | None] = mapped_column(String(32), default=None)
    status_message: Mapped[str | None] = mapped_column(String(255), default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
