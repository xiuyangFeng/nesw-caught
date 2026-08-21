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


class QuantFactorView(BaseModel):
    key: str
    sleeve: str
    horizon: str


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
    scenario: str = "real"
    trigger: str = "manual"

    @field_validator("scenario")
    @classmethod
    def scenario_must_be_known(cls, value: str) -> str:
        if value not in {"abstain", "mixed", "real"}:
            raise ValueError("scenario must be abstain, mixed or real")
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
    last_scheduled_run_date: date | None = None


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
    sleeve: str = "event_catalyst"
    state: str
    reason_code: str
    thesis_md: str | None = None
    evidence_grade: str | None = None
    event_type: str | None = None
    news_id: int | None = None


class QuantRadarView(BaseModel):
    as_of: UTCDateTime | None = None
    candidates: list[QuantRadarCandidateView] = Field(default_factory=list)
    note: str | None = None


class QuantResearchModuleView(BaseModel):
    key: str
    question: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    gap: str | None = None


class QuantResearchPackView(BaseModel):
    symbol: str
    display_name: str = ""
    modules: list[QuantResearchModuleView] = Field(default_factory=list)
    ask_ai_context: str = ""
    stale: bool = False


class QuantSymbolEventView(BaseModel):
    news_id: int | None = None
    title: str
    evidence_grade: str
    event_type: str
    state: str
    reason_code: str


class QuantAiRoleBindingView(BaseModel):
    role: str
    tier: str
    config_id: int | None = None


class QuantAiRoleBindingUpdate(BaseModel):
    role: str
    tier: str = "standard"
    config_id: int | None = None


class QuantAiAuditRowView(BaseModel):
    id: int
    role: str
    model: str
    prompt_version: str
    cache_hit: bool
    latency_ms: float
    token_in: int
    token_out: int
    status: str
    pool: str
    created_at: UTCDateTime


class QuantAiAuditView(BaseModel):
    items: list[QuantAiAuditRowView] = Field(default_factory=list)
    note: str | None = None


class QuantAiBudgetView(BaseModel):
    pools: dict[str, str] = Field(default_factory=dict)
    degrade_order: list[str] = Field(default_factory=list)
    note: str = "副驾预算独立；流水线预算耗尽只降级解释层。"


class QuantProposalItemView(BaseModel):
    symbol: str
    sleeve: str
    weight: float
    reject_reason: str | None = None


class QuantProposalView(BaseModel):
    cash_weight: float
    items: list[QuantProposalItemView] = Field(default_factory=list)
    note: str | None = None


class QuantReportCardView(BaseModel):
    window: str
    sleeves: dict[str, dict] = Field(default_factory=dict)
    sample_size: int = 0
    note: str | None = None


class QuantStrategyView(BaseModel):
    id: int
    name: str
    dsl: dict = Field(default_factory=dict)
    is_active: bool = False
    exploratory: bool = True
    errors: list[str] = Field(default_factory=list)


class QuantStrategyUpsert(BaseModel):
    name: str
    dsl: dict = Field(default_factory=dict)
    is_active: bool = False


class QuantStrategyUpdate(BaseModel):
    name: str | None = None
    dsl: dict | None = None
    is_active: bool | None = None


class QuantProposalExecuteItemView(BaseModel):
    symbol: str
    sleeve: str
    weight: float
    shares: int = 0
    filled: bool = False
    fill_price: float | None = None
    reject_reason: str | None = None


class QuantProposalExecuteView(BaseModel):
    cash_weight: float
    orders: list[QuantProposalExecuteItemView] = Field(default_factory=list)
    already_executed: bool = False
    note: str | None = None


class QuantBacktestView(BaseModel):
    id: int
    status: str
    exploratory: bool
    qualified: bool = False
    symbol: str = ""
    bars_used: int = 0
    equity_curve: list[dict] = Field(default_factory=list)
    trades: list[dict] = Field(default_factory=list)
    coverage_error: str | None = None
    metrics: dict = Field(default_factory=dict)
    note: str | None = None


class QuantBacktestRequest(BaseModel):
    name: str = ""
    dsl: dict = Field(default_factory=dict)
    is_active: bool = False
    symbol: str
    start_date: date | None = None
    end_date: date | None = None


class QuantPaperAccountView(BaseModel):
    id: int
    cash: float
    initial_cash: float
    note: str | None = None


class QuantPaperOrderRequest(BaseModel):
    symbol: str
    side: str = "buy"
    quantity: float = 100
    confirmed: bool = False


class QuantPaperOrderView(BaseModel):
    id: int | None = None
    status: str
    filled: bool = False
    reason: str | None = None
    price: float | None = None


class QuantDecisionLogView(BaseModel):
    items: list[dict] = Field(default_factory=list)


class QuantCopilotToolsView(BaseModel):
    tools: list[str] = Field(default_factory=list)
    note: str = "全部只读，副驾不能下单或改策略。"


