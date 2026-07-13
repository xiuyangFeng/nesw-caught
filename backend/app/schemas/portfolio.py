from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime
from app.schemas.news import NewsItemSummary


class PortfolioPositionView(BaseModel):
    """单只持仓的成本 / 盈亏 / 仓位权重明细。"""

    symbol: str
    market: str
    display_name: str
    position_size: float
    average_cost: float | None = None
    # 行情（缺失时为 None，price_status 说明原因）
    current_price: float | None = None
    change_percent: float | None = None
    price_status: str = "unavailable"
    price_message: str | None = None
    quote_fetched_at: UTCDateTime | None = None
    # 计算值：市值、成本、未实现盈亏（额与百分比）、组合权重（0~1）
    market_value: float | None = None
    cost_basis: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_percent: float | None = None
    weight: float | None = None


class PortfolioWeightedNewsView(BaseModel):
    """按仓位价值加权后、组合层“最该看”的一条新闻。"""

    news_item: NewsItemSummary
    # 命中该新闻的持仓 symbol（可能多只）
    symbols: list[str] = Field(default_factory=list)
    sentiment_score: float | None = None
    # signed_impact：带方向的加权影响分（sentiment_score × Σ命中持仓权重）
    # impact_score：其绝对值，用于排序
    signed_impact: float = 0.0
    impact_score: float = 0.0


class PortfolioSummaryView(BaseModel):
    """组合汇总：总市值 / 总盈亏 + 按仓位加权的新闻排序。"""

    generated_at: UTCDateTime
    position_count: int = 0
    priced_position_count: int = 0
    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_unrealized_pnl_percent: float | None = None
    positions: list[PortfolioPositionView] = Field(default_factory=list)
    weighted_news: list[PortfolioWeightedNewsView] = Field(default_factory=list)
