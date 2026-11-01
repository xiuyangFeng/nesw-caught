from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ImpactTargetType = Literal["stock", "sector"]
ImpactDirection = Literal["bullish", "bearish", "neutral"]
ImpactStrength = Literal["strong", "medium", "weak"]


class NewsAiScreenView(BaseModel):
    importance: int
    overseas: bool
    deep_read: bool
    title_zh: str | None = None
    reason: str | None = None
    status: str
    screened_at: datetime


class NewsAiAnalysisView(BaseModel):
    summary_zh: str | None = None
    view: str | None = None
    major: bool
    status: str
    error: str | None = None
    analyzed_at: datetime


class NewsImpactView(BaseModel):
    id: int
    target_type: ImpactTargetType
    code: str | None = None
    name: str
    direction: ImpactDirection
    strength: ImpactStrength
    rationale: str | None = None
    source: Literal["ai", "user"]


class NewsAiView(BaseModel):
    news_id: int
    screen: NewsAiScreenView | None = None
    analysis: NewsAiAnalysisView | None = None
    impacts: list[NewsImpactView] = Field(default_factory=list)


class ImpactInput(BaseModel):
    target_type: ImpactTargetType
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    direction: ImpactDirection
    strength: ImpactStrength
    rationale: str | None = Field(default=None, max_length=200)


class ImpactCorrectionRequest(BaseModel):
    impacts: list[ImpactInput] = Field(max_length=20)
    note: str | None = Field(default=None, max_length=500)


class StockImpactView(BaseModel):
    news_id: int
    news_title: str
    title_zh: str | None = None
    published_at: datetime | None = None
    direction: ImpactDirection
    strength: ImpactStrength
    rationale: str | None = None
    source: Literal["ai", "user"]
    view: str | None = None


class FocusSectorView(BaseModel):
    name: str
    source: Literal["ai", "user"]
    symbols: list[str] = Field(default_factory=list)


class FocusSectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class AiFunnelUsageView(BaseModel):
    operation_type: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None = None


class AiFunnelTodayView(BaseModel):
    screened: int
    screen_errors: int
    analyzed: int
    analysis_errors: int
    impacts: int
    analysis_daily_limit: int
    cost_usd: float | None = None


class AiFunnelErrorView(BaseModel):
    message: str | None = None
    at: datetime | None = None


class AiFunnelStatusView(BaseModel):
    enabled: bool
    active: bool
    inactive_reason: Literal["disabled", "no_default_model", "over_budget", "worker_not_running"] | None = None
    model_name: str | None = None
    model_display_name: str | None = None
    today: AiFunnelTodayView
    usage: list[AiFunnelUsageView]
    month_cost_usd: float | None = None
    monthly_budget_usd: float | None = None
    over_budget: bool
    last_error: AiFunnelErrorView | None = None
