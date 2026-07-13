"""统一系统健康看板（Ops Health Dashboard）的响应契约。

本模块只定义 API 出参结构，聚合逻辑全部在 ``app.services.ops_health`` 中。
所有时间字段统一走 ``UTCDateTime``，保证前端拿到带 ``Z`` 的 UTC ISO 串。
"""

from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class OpsAlert(BaseModel):
    """一条结构化告警。

    - ``level``：``warning`` 橙色 / ``critical`` 红色；
    - ``code``：稳定的机器可读标识（如 ``source.consecutive_failures``）；
    - ``subject``：出问题的资源标识（源名 / worker 名 / ``database`` / ``event_bus``）；
    - ``message``：面向人的中文说明。
    """

    level: str
    code: str
    subject: str
    message: str


class OpsWorkerView(BaseModel):
    """后台 worker 的运行时快照。"""

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
    # 距最近一次心跳的秒数（无心跳时为 None），供前端与阈值判定复用。
    heartbeat_age_seconds: float | None = None


class OpsSourceView(BaseModel):
    """新闻源健康快照。"""

    source_name: str
    market: str
    source_type: str
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    # 成功率（0..1 小数，四舍五入 4 位）；从未抓取时为 None。
    success_rate: float | None = None
    avg_latency_ms: float | None = None
    is_disabled: bool


class OpsXSourceView(BaseModel):
    """X（推特）数据源健康快照。"""

    provider_name: str
    last_success_at: UTCDateTime | None = None
    last_failure_at: UTCDateTime | None = None
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    success_rate: float | None = None
    avg_latency_ms: float | None = None
    last_error: str | None = None


class OpsLlmModelUsageView(BaseModel):
    """近窗口内单个模型的调用/token 用量。"""

    model_name: str
    call_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpsLlmUsageView(BaseModel):
    """近 ``window_hours`` 小时的 LLM 用量汇总。"""

    window_hours: int
    call_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    models: list[OpsLlmModelUsageView]


class OpsEventBusView(BaseModel):
    """事件层（event bus）状态与降级情况。"""

    backend: str
    status: str
    redis_enabled: bool
    last_published_at: UTCDateTime | None = None
    last_event_name: str | None = None
    last_error: str | None = None


class OpsDatabaseView(BaseModel):
    """SQLite 文件体积快照。"""

    path: str | None = None
    exists: bool
    size_bytes: int
    size_mb: float


class OpsHealthResponse(BaseModel):
    """健康看板聚合出参。

    ``overall_status`` 由 ``alerts`` 派生：存在 critical 则 critical，
    否则存在 warning 则 warning，否则 ok。
    """

    generated_at: UTCDateTime
    overall_status: str
    alerts: list[OpsAlert]
    workers: list[OpsWorkerView]
    sources: list[OpsSourceView]
    x_sources: list[OpsXSourceView]
    llm_usage: OpsLlmUsageView
    event_bus: OpsEventBusView
    database: OpsDatabaseView
