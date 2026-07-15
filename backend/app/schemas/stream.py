from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class MarketWorkerStatusView(BaseModel):
    name: str
    status: str
    last_heartbeat_at: UTCDateTime | None = None
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    last_error: str | None = None
    cycle_count: int
    success_count: int
    failure_count: int
    last_quotes_count: int


class StreamStatusResponse(BaseModel):
    mode: str
    status: str
    backend: str
    redis_enabled: bool
    last_published_at: UTCDateTime | None = None
    last_event_name: str | None = None
    last_error: str | None = None
    market_worker: MarketWorkerStatusView | None = None
