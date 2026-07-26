import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.routes.stream import get_active_stream_connection_count
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.llm_token_usage import LLMTokenUsage
from app.models.source_health import SourceHealth
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.models.x_source_health import XSourceHealth
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.health import AiServiceStatus, HealthResponse, SourceHealthSummary
from app.schemas.source_health import SourceHealthView
from app.schemas.x_monitor import XHealthResponse
from app.services.x_monitor import PROVIDER_NAME, XMonitorService

router = APIRouter()
logger = logging.getLogger(__name__)

MARKET_QUOTE_WORKER_NAME = "market_quote_producer"


def _check_database(session: Session) -> bool:
    """执行一次轻量 SELECT 1，探测数据库连通性；不抛异常，失败即返回 False。"""
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - 数据库不可用时的兜底分支
        logger.exception("health check: database connectivity probe failed")
        return False


def _last_rss_fetch_at(session: Session) -> datetime | None:
    """所有 source_type="rss" 新闻源里最近一次成功抓取时间的全局最大值。"""
    stmt = select(func.max(SourceHealth.last_success_at)).where(SourceHealth.source_type == "rss")
    return session.scalar(stmt)


def _last_market_quote_refresh_at(session: Session) -> datetime | None:
    stmt = select(WorkerRuntimeStatus.last_success_at).where(
        WorkerRuntimeStatus.worker_name == MARKET_QUOTE_WORKER_NAME
    )
    return session.scalar(stmt)


def _source_health_summary(repository: SourceHealthRepository) -> SourceHealthSummary:
    rows = repository.list_all()
    return SourceHealthSummary(
        total=len(rows),
        disabled=sum(1 for row in rows if row.is_disabled),
        consecutive_failing=sum(1 for row in rows if row.consecutive_failures > 0),
    )


def _ai_status(session: Session, settings) -> AiServiceStatus:
    """AI 服务状态：以 settings.ai_enabled 为开关位，最近一次 LLM 调用时间取自用量流水表，
    作为存活参考（当前没有专门的 LLM provider 健康记录表可查）。"""
    last_call_at: datetime | None = None
    if settings.ai_enabled:
        stmt = select(func.max(LLMTokenUsage.created_at))
        last_call_at = session.scalar(stmt)
    return AiServiceStatus(enabled=settings.ai_enabled, last_call_at=last_call_at)


def _x_monitor_healthy_from_cache(session: Session, settings) -> bool:
    """从「上一次探测结果」推断 X 监控健康度——**绝不在请求线程里联网**。

    此前这里直接调 ``XMonitorService.provider_health()``，它会对 twitterapi.io
    发起真实 HTTP 探针（``TWITTERAPI_IO_TIMEOUT_SECONDS=60``，探针缓存 TTL 只有
    30 秒）。而 /health 是前端轮询接口，等于每 30 秒就有一个请求线程被最长 60 秒
    的外网调用占住，并且全程攥着一条 SQLite 连接。

    现在改为读 ``x_source_health`` 里由后台刷新 / 手动 ``POST /api/x/refresh``
    / ``GET /api/health/x`` 记录下来的结果：
    - 没有记录、或记录已陈旧（超出刷新冷却期的 2 倍）→ 视为 unknown，返回 False；
    - 有连续失败 → False。
    实时探针仍然保留在按需调用的 ``GET /api/health/x`` 上。
    """
    if not settings.x_monitor_enabled:
        return False
    if not getattr(settings, "twitterapi_io_api_key", None):
        return False

    try:
        row = session.scalar(select(XSourceHealth).where(XSourceHealth.provider_name == PROVIDER_NAME))
    except Exception:  # pragma: no cover - 数据库不可用时的兜底分支
        logger.exception("health check: x monitor health lookup failed")
        return False

    if row is None or row.last_success_at is None or row.consecutive_failures > 0:
        return False

    last_success_at = row.last_success_at
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=UTC)
    cooldown_hours = float(getattr(settings, "x_monitor_refresh_cooldown_hours", 3) or 3)
    stale_after = timedelta(hours=max(6.0, cooldown_hours * 2))
    if datetime.now(UTC) - last_success_at > stale_after:
        # 陈旧 = unknown：宁可报不健康，也不在请求路径上花 60 秒去问一次。
        return False
    return True


@router.get("/health", response_model=HealthResponse)
def health_check(session: Session = Depends(get_db_session)) -> HealthResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    x_monitor_healthy = _x_monitor_healthy_from_cache(session, settings)

    database_healthy = _check_database(session)
    source_health_repository = SourceHealthRepository(session)

    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        now_utc=now,
        database="ok" if database_healthy else "unavailable",
        stream_mode=settings.stream_mode,
        ai_enabled=settings.ai_enabled,
        x_monitor_enabled=settings.x_monitor_enabled,
        x_monitor_healthy=x_monitor_healthy,
        database_healthy=database_healthy,
        last_rss_fetch_at=_last_rss_fetch_at(session),
        last_market_quote_refresh_at=_last_market_quote_refresh_at(session),
        source_health_summary=_source_health_summary(source_health_repository),
        active_stream_connections=get_active_stream_connection_count(),
        ai_status=_ai_status(session, settings),
    )


@router.get("/health/sources", response_model=list[SourceHealthView])
def list_source_health(session: Session = Depends(get_db_session)) -> list[SourceHealthView]:
    repository = SourceHealthRepository(session)
    return [SourceHealthView.model_validate(item, from_attributes=True) for item in repository.list_all()]


@router.get("/health/x", response_model=XHealthResponse)
def x_health_check(session: Session = Depends(get_db_session)) -> XHealthResponse:
    settings = get_settings()
    service = XMonitorService(session)
    healthy, status = service.provider_health()
    health = service.health_repo.get_or_create(PROVIDER_NAME)
    session.commit()
    return XHealthResponse(
        enabled=settings.x_monitor_enabled,
        configured=bool(settings.twitterapi_io_api_key),
        healthy=healthy,
        status=status,
        provider_name=health.provider_name,
        min_interval_seconds=float(settings.twitterapi_io_min_interval_seconds),
        refresh_cooldown_hours=int(settings.x_monitor_refresh_cooldown_hours),
        last_success_at=health.last_success_at,
        last_failure_at=health.last_failure_at,
        consecutive_failures=health.consecutive_failures,
        total_fetches=health.total_fetches,
        total_failures=health.total_failures,
        avg_latency_ms=health.avg_latency_ms,
        last_error=health.last_error,
    )
