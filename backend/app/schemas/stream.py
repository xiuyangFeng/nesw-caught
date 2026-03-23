from app.schemas.common import UTCDateTime
from pydantic import BaseModel


class StreamStatusResponse(BaseModel):
    mode: str
    status: str
    backend: str
    redis_enabled: bool
    last_published_at: UTCDateTime | None = None
    last_event_name: str | None = None
    last_error: str | None = None
