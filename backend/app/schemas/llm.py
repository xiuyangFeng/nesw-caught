from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class LLMConfigUpsertRequest(BaseModel):
    id: int | None = None
    provider_name: str
    display_name: str | None = None
    base_url: str | None = None
    model_name: str
    api_key: str | None = None
    is_active: bool = True
    is_default: bool = False
    # 成本治理（非敏感、可选）：每 1K tokens 输入/输出单价与月度预算（美元）。
    input_price_per_1k: float | None = None
    output_price_per_1k: float | None = None
    monthly_budget_usd: float | None = None


class LLMConfigView(BaseModel):
    configured: bool
    id: int | None = None
    provider_name: str | None = None
    display_name: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_key_set: bool = False
    is_active: bool = True
    is_default: bool = False
    input_price_per_1k: float | None = None
    output_price_per_1k: float | None = None
    monthly_budget_usd: float | None = None
    updated_at: UTCDateTime | None = None


class LLMOverallStatView(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # 按各模型单价换算的累计花费（美元）；无任何模型配置单价时为 null。
    cost_usd: float | None = None
    cost_available: bool = False


class LLMModelStatView(BaseModel):
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    call_count: int
    # 该模型换算后的花费（美元）；未配置单价时为 null 并以 cost_available 标注。
    cost_usd: float | None = None
    cost_available: bool = False
    input_price_per_1k: float | None = None
    output_price_per_1k: float | None = None


class LLMOperationStatView(BaseModel):
    operation_type: str
    total_tokens: int


class LLMDailyStatView(BaseModel):
    date: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMBudgetView(BaseModel):
    # 当前统计所属月份（YYYY-MM）。
    month: str
    # 本月累计花费（美元）；无单价时为 null。
    month_cost_usd: float | None = None
    # 默认模型配置上设置的月度预算（美元）；未设置时为 null。
    monthly_budget_usd: float | None = None
    budget_available: bool = False
    over_budget: bool = False
    # 本月花费 / 预算；任一缺失时为 null。
    usage_ratio: float | None = None


class LLMStatsView(BaseModel):
    overall: LLMOverallStatView
    models: list[LLMModelStatView]
    operations: list[LLMOperationStatView]
    daily: list[LLMDailyStatView]
    budget: LLMBudgetView


class LLMChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []
    news_id: int | None = None
    config_id: int | None = None
    stream: bool = True


class LLMTranslateRequest(BaseModel):
    text: str


class LLMTranslateView(BaseModel):
    provider_name: str
    model_name: str
    translated_text: str


class LLMConnectionTestView(BaseModel):
    provider_name: str
    model_name: str
    message: str
    latency_ms: float | None = None


class LLMAnalysisCandidate(BaseModel):
    symbol: str
    market: str
    company_name: str | None = None
    confidence: float | None = None
    reason: str


class NewsAnalysisView(BaseModel):
    news_id: int
    provider_name: str
    model_name: str
    analysis_status: str
    top_pick: LLMAnalysisCandidate | None = None
    candidates: list[LLMAnalysisCandidate]
    summary: str | None = None
    risk_notes: str | None = None
    sentiment: str | None = None
    context_limitations: str | None = None
    analyzed_at: UTCDateTime
    analysis_error: str | None = None
