from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class FeishuConfigUpsertRequest(BaseModel):
    app_id: str
    app_secret: str | None = None
    target_type: str = "chat"
    target_id: str
    news_enabled: bool = True
    news_keywords: str | None = None
    news_batch_interval_minutes: int = 60
    alert_enabled: bool = True
    analysis_enabled: bool = True
    is_active: bool = True


class FeishuConfigView(BaseModel):
    configured: bool
    app_id: str | None = None
    app_secret_set: bool = False
    target_type: str | None = None
    target_id: str | None = None
    news_enabled: bool = True
    news_keywords: str | None = None
    news_batch_interval_minutes: int = 60
    alert_enabled: bool = True
    analysis_enabled: bool = True
    is_active: bool = True
    updated_at: UTCDateTime | None = None


class FeishuTestResult(BaseModel):
    success: bool
    message: str
