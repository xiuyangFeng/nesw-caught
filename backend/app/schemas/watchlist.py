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


class WatchlistItemView(BaseModel):
    id: int
    symbol: str
    market: str
    display_name: str
    is_active: bool
    alert_threshold: float | None = None
    alert_mode: str


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
