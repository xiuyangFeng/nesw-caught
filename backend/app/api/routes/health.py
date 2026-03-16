from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        now_utc=now,
        database="configured",
        stream_mode=settings.stream_mode,
        ai_enabled=settings.ai_enabled,
    )
