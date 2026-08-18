from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UTCDateTime


class QuantRecommendationItemView(BaseModel):
    symbol: str
    display_name: str = ""
    sleeve: str
    horizon: str
    state: str
    rank: int | None = None
    deterministic_score: float
    score_calibrated: bool = False
    reason_code: str
    factor_breakdown: dict[str, float] = Field(default_factory=dict)
    thesis_md: str | None = None
    invalidation_condition: str | None = None
    valid_until: date | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class QuantRunStageView(BaseModel):
    stage: str
    status: str
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None = None
    detail: dict = Field(default_factory=dict)


class QuantRecommendationRunView(BaseModel):
    id: int
    run_date: date
    source_cutoff: UTCDateTime
    trigger: str
    status: str
    scenario: str
    dataset_version: str
    factor_version: str
    rule_version: str
    code_commit: str
    result_hash: str
    empty_reason: str | None = None
    empty_reason_detail: str | None = None
    started_at: UTCDateTime
    finished_at: UTCDateTime | None = None
    stages: list[QuantRunStageView] = Field(default_factory=list)


class QuantRecommendationLatestView(BaseModel):
    available: bool = True
    run: QuantRecommendationRunView | None = None
    items: list[QuantRecommendationItemView] = Field(default_factory=list)
    empty_reason: str | None = None
    empty_reason_detail: str | None = None


class QuantRunRequest(BaseModel):
    scenario: str = "abstain"
    trigger: str = "manual"

    @field_validator("scenario")
    @classmethod
    def scenario_must_be_known(cls, value: str) -> str:
        if value not in {"abstain", "mixed"}:
            raise ValueError("scenario must be abstain or mixed")
        return value


class QuantDataStatusView(BaseModel):
    regime: str = "normal"
    coverage_pct: float | None = None
    source_cutoff: UTCDateTime | None = None
    dataset_version: str
    factor_version: str
    rule_version: str
    pit_ready: bool = True
    backfill_progress_pct: float = 0
    note: str
    last_run_status: str | None = None
    daily_bar_count: int = 0
    symbol_count: int = 0
    fund_flow_count: int = 0
    last_trade_date: date | None = None


class QuantFundFlowPointView(BaseModel):
    trade_date: date
    main_net_inflow: float | None = None
    super_large_net: float | None = None
    large_net: float | None = None
    medium_net: float | None = None
    small_net: float | None = None
    main_net_pct: float | None = None


class QuantFundFlowView(BaseModel):
    symbol: str
    points: list[QuantFundFlowPointView] = Field(default_factory=list)
    note: str | None = None


class QuantRadarCandidateView(BaseModel):
    symbol: str
    display_name: str = ""
    sleeve: str
    state: str
    reason_code: str
    thesis_md: str | None = None


class QuantRadarView(BaseModel):
    as_of: UTCDateTime | None = None
    candidates: list[QuantRadarCandidateView] = Field(default_factory=list)
    note: str | None = None
