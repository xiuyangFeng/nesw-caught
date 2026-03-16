from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class XAccountView(BaseModel):
    id: int
    handle: str
    display_name: str
    market_focus: str | None = None
    is_active: bool
    priority: int
    notes: str | None = None


class XPostSummaryView(BaseModel):
    id: int
    account_handle: str
    account_display_name: str
    content_text: str
    canonical_url: str | None = None
    market: str
    sentiment_label: str
    relevance_score: float | None = None
    posted_at: UTCDateTime | None = None
    captured_at: UTCDateTime
    symbols: list[str]


class XRefreshResponse(BaseModel):
    started_at: UTCDateTime
    finished_at: UTCDateTime
    fetched_count: int
    inserted_count: int
    error: str | None = None
    latency_ms: float


class XHealthResponse(BaseModel):
    enabled: bool
    bridge_configured: bool
    bridge_healthy: bool
    bridge_status: str
    provider_name: str
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    avg_latency_ms: float | None = None
    last_error: str | None = None
