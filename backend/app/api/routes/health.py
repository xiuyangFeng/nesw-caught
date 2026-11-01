import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.routes.stream import get_active_stream_connection_count
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.llm_token_usage import LLMTokenUsage
from app.models.source_health import SourceHealth
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.health import AiServiceStatus, HealthResponse, SourceHealthSummary
from app.schemas.source_health import SourceHealthView

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


@router.get("/health", response_model=HealthResponse)
def health_check(session: Session = Depends(get_db_session)) -> HealthResponse:
    settings = get_settings()
    now = datetime.now(UTC)
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

