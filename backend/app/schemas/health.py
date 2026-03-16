from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    now_utc: datetime
    database: str
    stream_mode: str
    ai_enabled: bool
