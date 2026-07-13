from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime
from app.schemas.news import NewsItemSummary


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market: str
    display_name: str = Field(min_length=1, max_length=120)
    alert_threshold: float | None = None
    alert_mode: str = "fixed"


class WatchlistItemUpdate(BaseModel):
    """自选股更新模型：目前用于写入持仓量 / 平均成本（持仓/组合视图）。

    字段均可选，仅提交的字段会被写入（未提交字段保持原值不变）。
    position_size / average_cost 传 null 表示“清空持仓”。
    """

    position_size: float | None = Field(default=None, ge=0)
    average_cost: float | None = Field(default=None, ge=0)


class WatchlistItemView(BaseModel):
    id: int
    symbol: str
    market: str
    display_name: str
    is_active: bool
    alert_threshold: float | None = None
    alert_mode: str
    position_size: float | None = None
    average_cost: float | None = None


class WatchlistCandidateView(BaseModel):
    symbol: str
    market: str
    display_name: str
    aliases: list[str] = []


ResearchDriverCategory = Literal["policy_macro", "company_action", "supply_chain", "price_action"]
ResearchActionLevel = Literal["act_now", "watch_today", "know_only"]
ResearchTopActionLevel = Literal["act_now", "watch_today", "know_only", "none"]


class WatchlistResearchDriverView(BaseModel):
    category: ResearchDriverCategory
    action_level: ResearchActionLevel
    reason: str
    news_item: NewsItemSummary


class WatchlistResearchBriefView(BaseModel):
    symbol: str
    market: str
    generated_at: UTCDateTime
    window_days: int = 14
    top_action_level: ResearchTopActionLevel
    has_unexplained_price_move: bool = False
    drivers: list[WatchlistResearchDriverView] = Field(default_factory=list)


class WatchlistAiInsightView(BaseModel):
    symbol: str
    insight_text: str
    generated_at: UTCDateTime
    failover: dict[str, str] | None = None
