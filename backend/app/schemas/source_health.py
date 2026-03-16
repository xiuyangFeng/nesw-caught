from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class SourceHealthView(BaseModel):
    source_name: str
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
