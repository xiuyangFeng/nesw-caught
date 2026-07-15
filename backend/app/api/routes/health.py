from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.health import HealthResponse
from app.schemas.source_health import SourceHealthView
from app.schemas.x_monitor import XHealthResponse
from app.services.x_monitor import PROVIDER_NAME, XMonitorService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(session: Session = Depends(get_db_session)) -> HealthResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    x_monitor_healthy = False
    if settings.x_monitor_enabled:
        service = XMonitorService(session)
        x_monitor_healthy, _ = service.provider_health()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        now_utc=now,
        database="configured",
        stream_mode=settings.stream_mode,
        ai_enabled=settings.ai_enabled,
        x_monitor_enabled=settings.x_monitor_enabled,
        x_monitor_healthy=x_monitor_healthy,
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
