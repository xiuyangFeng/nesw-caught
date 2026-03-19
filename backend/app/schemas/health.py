from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    now_utc: UTCDateTime
    database: str
    stream_mode: str
    ai_enabled: bool
    x_monitor_enabled: bool = False
    x_monitor_healthy: bool = False
