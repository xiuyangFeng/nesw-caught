"""个股 AI 综合研判（本地语料 RAG）结构化研报 Schema。

后端把某只股票近 N 天的命中新闻（标题/摘要/正文）与最近价格走势综合成一份
结构化 JSON 研报：评级 / 催化剂（bull_case）/ 风险（bear_case）/ 关键时间线
（key_events）/ 摘要。LLM 不可用时降级为基于规则的要点汇总，字段结构保持一致。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime

# 综合评级：偏多 / 中性 / 偏空 / 未知（数据不足时）
StockResearchRating = Literal[
    "strong_bullish",
    "bullish",
    "neutral",
    "bearish",
    "strong_bearish",
    "unknown",
]

# 研报生成方式：llm=大模型综合；rule=大模型不可用时的规则降级。
StockResearchMode = Literal["llm", "rule"]

# 关键事件对标的的方向性影响。
EventImpact = Literal["positive", "negative", "neutral"]


class StockResearchKeyEvent(BaseModel):
    """关键时间线上的单个事件。"""

    date: str | None = None
    title: str
    description: str | None = None
    impact: EventImpact = "neutral"


class StockResearchReference(BaseModel):
    """研报所引用的单条命中新闻（可回溯本地语料）。"""

    news_id: int
    title: str
    source_name: str
    canonical_url: str | None = None
    published_at: UTCDateTime | None = None
    sentiment_label: str | None = None


class StockResearchPriceContext(BaseModel):
    """近 N 天价格走势快照上下文。"""

    price: float | None = None
    change_percent: float | None = None
    window_high: float | None = None
    window_low: float | None = None
    window_change_percent: float | None = None
    snapshot_count: int = 0
    status: str | None = None


class StockResearchReport(BaseModel):
    """个股 AI 综合研判结构化研报响应。"""

    symbol: str
    market: str
    display_name: str | None = None
    generated_at: UTCDateTime
    lookback_days: int
    mode: StockResearchMode
    overall_rating: StockResearchRating
    rating_rationale: str | None = None
    summary: str
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    key_events: list[StockResearchKeyEvent] = Field(default_factory=list)
    price_context: StockResearchPriceContext
    references: list[StockResearchReference] = Field(default_factory=list)
    news_count: int = 0
    model_name: str | None = None
    llm_error: str | None = None
    failover: dict[str, str] | None = None
