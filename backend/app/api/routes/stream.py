import json
from queue import Empty, Queue

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.session import get_db_session
from app.schemas.stream import MarketWorkerStatusView, StreamStatusResponse
from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository
from app.services.event_bus import get_event_bus

router = APIRouter()
STREAM_EVENT_NAMES = ("news.created", "news.updated")
STREAM_KEEPALIVE_SECONDS = 15


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


@router.get("/events")
def stream_events(limit: int | None = None) -> StreamingResponse:
    event_bus = get_event_bus()
    queue: Queue[tuple[str, dict[str, object], datetime]] = Queue()
    handlers: dict[str, object] = {}

    for event_name in STREAM_EVENT_NAMES:
        def _handler(payload: dict[str, object], *, _event_name: str = event_name) -> None:
            queue.put((_event_name, payload, _utc_now()))

        handlers[event_name] = _handler
        event_bus.subscribe(event_name, _handler)

    def _event_stream():
        sent = 0
        try:
            while limit is None or sent < limit:
                try:
                    event_name, payload, occurred_at = queue.get(timeout=STREAM_KEEPALIVE_SECONDS)
                    envelope = {
                        "type": event_name,
                        "occurred_at": _serialize_timestamp(occurred_at),
                        "payload": payload,
                    }
                except Empty:
                    envelope = {
                        "type": "stream.keepalive",
                        "occurred_at": _serialize_timestamp(_utc_now()),
                        "payload": {"status": "ok"},
                    }
                yield f"data: {json.dumps(envelope, separators=(',', ':'))}\n\n"
                sent += 1
        finally:
            for event_name, handler in handlers.items():
                unsubscribe = getattr(event_bus, "unsubscribe", None)
                if unsubscribe is not None:
                    unsubscribe(event_name, handler)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
