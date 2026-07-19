from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class SourceHealthSummary(BaseModel):
    """数据源健康汇总，避免请求方再单独调用 /health/sources 拼接。"""

    total: int = 0
    disabled: int = 0
    consecutive_failing: int = 0


class AiServiceStatus(BaseModel):
    """AI 服务状态：是否启用 + 最近一次 LLM 调用时间（无专门的 provider 健康表可查，用作存活参考）。"""

    enabled: bool = False
    last_call_at: UTCDateTime | None = None


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
    # 数据库真实连通性探测结果：执行一次轻量 SELECT 1 判定，而非硬编码字符串。
    database_healthy: bool = False
    # 全站 source_type="rss" 新闻源里最近一次成功抓取的时间（取全局最大值）；无记录时为 None。
    last_rss_fetch_at: UTCDateTime | None = None
    # market_quote_producer worker 最近一次成功刷新行情的时间；未运行过则为 None。
    last_market_quote_refresh_at: UTCDateTime | None = None
    # 数据源健康汇总。
    source_health_summary: SourceHealthSummary
    # 当前进程内存活的 SSE (`/events`) 推送连接数。
    active_stream_connections: int = 0
    # AI 服务状态。
    ai_status: AiServiceStatus
