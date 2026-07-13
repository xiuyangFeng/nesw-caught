from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class AlertGovernanceUpdate(BaseModel):
    """告警治理运行期覆盖（保存在 NotificationService 内存，不落库）。全部可选。"""

    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_tz: str | None = None
    dedupe_window_minutes: int | None = None
    digest_window_minutes: int | None = None
    digest_threshold: int | None = None
    critical_change_percent: float | None = None


class AlertGovernanceView(BaseModel):
    """治理当前生效值（settings 默认叠加内存覆盖后的结果），供前端回显。"""

    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_tz: str = "Asia/Shanghai"
    dedupe_window_minutes: int = 0
    digest_window_minutes: int = 0
    digest_threshold: int = 3
    critical_change_percent: float = 8.0


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
    governance: AlertGovernanceUpdate | None = None


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
    governance: AlertGovernanceView | None = None


class FeishuTestResult(BaseModel):
    success: bool
    message: str
