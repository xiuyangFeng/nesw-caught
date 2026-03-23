from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.stream import MarketWorkerStatusView, StreamStatusResponse
from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository
from app.services.event_bus import get_event_bus

router = APIRouter()


def get_market_worker_runtime_status(session: Session) -> dict[str, object] | None:
    status = WorkerRuntimeStatusRepository(session).get_by_name("market_quote_producer")
    if status is None:
        return None
    return {
        "name": status.worker_name,
        "status": status.status,
        "last_heartbeat_at": status.last_heartbeat_at,
        "last_success_at": status.last_success_at,
        "last_failure_at": status.last_failure_at,
        "last_error": status.last_error,
        "cycle_count": status.cycle_count,
        "success_count": status.success_count,
        "failure_count": status.failure_count,
        "last_quotes_count": status.last_quotes_count,
    }


@router.get("/status", response_model=StreamStatusResponse)
def stream_status(session: Session = Depends(get_db_session)) -> StreamStatusResponse:
    status = get_event_bus().get_status()
    market_worker = get_market_worker_runtime_status(session)
    return StreamStatusResponse(
        mode="sse",
        status=status.status,
        backend=status.backend,
        redis_enabled=status.redis_enabled,
        last_published_at=status.last_published_at,
        last_event_name=status.last_event_name,
        last_error=status.last_error,
        market_worker=MarketWorkerStatusView.model_validate(market_worker) if market_worker else None,
    )
