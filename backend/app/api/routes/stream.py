from fastapi import APIRouter

from app.schemas.stream import StreamStatusResponse
from app.services.event_bus import get_event_bus

router = APIRouter()


@router.get("/status", response_model=StreamStatusResponse)
def stream_status() -> StreamStatusResponse:
    status = get_event_bus().get_status()
    return StreamStatusResponse(
        mode="sse",
        status=status.status,
        backend=status.backend,
        redis_enabled=status.redis_enabled,
        last_published_at=status.last_published_at,
        last_event_name=status.last_event_name,
        last_error=status.last_error,
    )
