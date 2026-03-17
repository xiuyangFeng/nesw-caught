from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class LLMConfigUpsertRequest(BaseModel):
    provider_name: str
    display_name: str | None = None
    base_url: str | None = None
    model_name: str
    api_key: str


class LLMConfigView(BaseModel):
    configured: bool
    provider_name: str | None = None
    display_name: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key_set: bool = False
    updated_at: UTCDateTime | None = None


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
