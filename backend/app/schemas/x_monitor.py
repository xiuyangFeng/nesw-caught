from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UTCDateTime


class XAccountView(BaseModel):
    id: int
    handle: str
    display_name: str
    market_focus: str | None = None
    is_active: bool
    priority: int
    tier: str
    source: str
    notes: str | None = None


class XAccountCreateRequest(BaseModel):
    handle: str
    display_name: str
    market_focus: str | None = None
    is_active: bool = True
    priority: int = 0
    tier: str = "watch"
    notes: str | None = None

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        normalized = value.lstrip("@").strip()
        if not normalized:
            raise ValueError("handle is required")
        return normalized

    @field_validator("tier")
    @classmethod
    def normalize_tier(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"core", "watch", "muted"}:
            raise ValueError("tier must be core, watch, or muted")
        return normalized


class XAccountUpdateRequest(BaseModel):
    display_name: str | None = None
    market_focus: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    tier: str | None = None
    notes: str | None = None

    @field_validator("tier")
    @classmethod
    def normalize_tier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"core", "watch", "muted"}:
            raise ValueError("tier must be core, watch, or muted")
        return normalized


class XAccountsImportResult(BaseModel):
    created_count: int
    updated_count: int
    skipped_count: int = 0


class XAccountsExportResult(BaseModel):
    exported_count: int


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
    skipped: bool = False
    skip_reason: str | None = None
    next_refresh_at: UTCDateTime | None = None


class XRadarSignalView(BaseModel):
    id: int
    signal_type: str
    title: str
    summary: str
    market: str
    topic_tag: str | None = None
    macro_tag: str | None = None
    primary_symbol: str | None = None
    priority_score: float
    confidence_score: float
    source_count: int
    first_seen_at: UTCDateTime
    last_seen_at: UTCDateTime


class XRadarMacroClusterView(BaseModel):
    macro_tag: str
    title: str
    signal_count: int
    source_count: int
    top_signal_ids: list[int] = Field(default_factory=list)


class XRadarResponse(BaseModel):
    priority_signals: list[XRadarSignalView]
    macro_clusters: list[XRadarMacroClusterView]
    evidence_stream: list[XPostSummaryView]


class XHealthResponse(BaseModel):
    enabled: bool
    configured: bool
    healthy: bool
    status: str
    provider_name: str
    min_interval_seconds: float = 0.0
    refresh_cooldown_hours: int = 3
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    avg_latency_ms: float | None = None
    last_error: str | None = None
