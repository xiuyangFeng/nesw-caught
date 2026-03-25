from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class SourceHealthView(BaseModel):
    source_name: str
    market: str
    source_type: str
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    avg_latency_ms: float | None = None
    is_disabled: bool


class SourceFetchResultView(BaseModel):
    source_name: str
    source_type: str
    status: str
    fetched_count: int
    inserted_count: int
    error: str | None = None
    latency_ms: float


class NewsRefreshResponse(BaseModel):
    started_at: UTCDateTime
    finished_at: UTCDateTime
    fetched_count: int
    inserted_count: int
    results: list[SourceFetchResultView]


class NewsRuntimeSourceView(BaseModel):
    source_name: str
    market: str
    tier: str
    status: str
    last_attempt_at: UTCDateTime | None = None
    last_success_at: UTCDateTime | None = None
    consecutive_failures: int
    avg_fetch_latency_ms: float | None = None
    latest_news_published_at: UTCDateTime | None = None
    latest_news_fetched_at: UTCDateTime | None = None
    last_error: str | None = None


class NewsRuntimeMarketView(BaseModel):
    market: str
    status: str
    mode: str
    last_primary_success_at: UTCDateTime | None = None
    last_news_created_at: UTCDateTime | None = None
    degraded_reason: str | None = None


class NewsRuntimeView(BaseModel):
    feed_status: str
    last_refresh_finished_at: UTCDateTime | None = None
    last_news_created_at: UTCDateTime | None = None
    last_incremental_event_at: UTCDateTime | None = None
    degraded_market_count: int
    markets: list[NewsRuntimeMarketView]
    sources: list[NewsRuntimeSourceView]
