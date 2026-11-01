"""关注板块（聚焦改造 P3）。

关注板块 = 自选股（含持仓）的 ``StockSector`` 并集 + 用户手动 add − 用户手动 remove。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

OVERRIDE_ADD = "add"
OVERRIDE_REMOVE = "remove"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class StockSector(Base):
    __tablename__ = "stock_sector"
    __table_args__ = (UniqueConstraint("symbol", "sector", name="ux_stock_sector_symbol_sector"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    sector: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class FocusSectorOverride(Base):
    __tablename__ = "focus_sector_override"

    id: Mapped[int] = mapped_column(primary_key=True)
    sector: Mapped[str] = mapped_column(String(64), unique=True)
    action: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
