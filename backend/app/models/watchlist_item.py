from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    alert_threshold: Mapped[float | None] = mapped_column(Float(), default=None)
    alert_mode: Mapped[str] = mapped_column(String(16), default="fixed")
    # 持仓/组合视图字段：记录该自选股的持仓数量与平均成本（均可空，
    # 未填写即视为“仅关注、无持仓”，不参与组合盈亏与加权新闻计算）。
    position_size: Mapped[float | None] = mapped_column(Float(), default=None)
    average_cost: Mapped[float | None] = mapped_column(Float(), default=None)
