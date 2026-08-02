from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MarketIndexConfig(TimestampMixin, Base):
    """市场总览的指数/板块代理 ETF 配置（单用户全局，无 user_id）。

    - symbol 存 Yahoo 原始 ticker（如 ``^GSPC``、``000300.SS``、``XLK``），
      不经过 normalize_symbol；
    - kind 区分 ``index``（指数，参与量化情绪计算）与 ``etf``（板块代理 ETF，
      仅展示用）；
    - enabled 是软开关，删除之外的禁用手段。
    """

    __tablename__ = "market_index_config"
    __table_args__ = (
        UniqueConstraint("symbol", "market", name="uq_market_index_config_symbol_market"),
        # 支撑 overview 查询：按市场取 enabled 条目并按 sort_order 排序。
        Index("ix_market_index_config_market_enabled_sort", "market", "enabled", "sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    market: Mapped[str] = mapped_column(String(16), index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="index")
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
    enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    # created_at 由 TimestampMixin 提供；updated_at 对齐 news_signal_result 的写法。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
