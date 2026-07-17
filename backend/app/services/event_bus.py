from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.services.redis_stream_bus import RedisStreamPublisher

EventHandler = Callable[[dict[str, Any]], None]


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class EventBusStatus:
    backend: str
    status: str
    redis_enabled: bool
    last_published_at: datetime | None = None
    last_event_name: str | None = None
    last_error: str | None = None


class InMemoryEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self.last_error: str | None = None

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_name)
        if not handlers:
            return
        self._handlers[event_name] = [item for item in handlers if item is not handler]
        if not self._handlers[event_name]:
            self._handlers.pop(event_name, None)

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        import logging
        logger = logging.getLogger(__name__)
        self.last_error = None
        for handler in self._handlers[event_name]:
            try:
                handler(payload)
            except Exception as exc:
                handler_name = getattr(handler, "__name__", str(handler))
                logger.exception(
                    f"EventBus handler '{handler_name}' failed on event '{event_name}'"
                )
                self.last_error = f"Handler '{handler_name}' failed on event '{event_name}': {exc}"


class HybridEventBus:
    def __init__(
        self,
        *,
        backend: str,
        local_bus: InMemoryEventBus | None = None,
        redis_publisher: RedisStreamPublisher | Any | None = None,
        stream_map: dict[str, str] | None = None,
        publisher_id: str | None = None,
    ) -> None:
        self.backend = backend
        self.local_bus = local_bus or InMemoryEventBus()
        self.redis_publisher = redis_publisher
        self.stream_map = stream_map or {}
        self.publisher_id = publisher_id or getattr(redis_publisher, "publisher_id", None) or uuid4().hex
        if redis_publisher is not None and getattr(redis_publisher, "publisher_id", None) is None:
            redis_publisher.publisher_id = self.publisher_id
        self._status = EventBusStatus(
            backend=backend,
            status="ok",
            redis_enabled=backend in {"hybrid", "redis"} and redis_publisher is not None,
        )

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self.local_bus.subscribe(event_name, handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        self.local_bus.unsubscribe(event_name, handler)

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        self._status.last_event_name = event_name
        self._status.last_published_at = _utc_now()

        should_publish_to_redis = self.backend in {"hybrid", "redis"} and self.redis_publisher is not None
        if should_publish_to_redis:
            stream_name = self.stream_map.get(event_name)
            if stream_name:
                try:
                    self.redis_publisher.publish(stream_name, payload, event_name=event_name)
                    self._status.status = "ok"
                    self._status.last_error = None
                except Exception as exc:  # pragma: no cover - exercised via tests with fakes
                    self._status.status = "degraded"
                    self._status.last_error = str(exc)

        self.local_bus.publish(event_name, payload)
        if self.local_bus.last_error:
            self._status.status = "degraded"
            self._status.last_error = self.local_bus.last_error

    def inject_from_remote(self, event_name: str, payload: dict[str, Any]) -> None:
        """Inject a cross-process event into local subscribers only (no Redis echo)."""
        self._status.last_event_name = event_name
        self._status.last_published_at = _utc_now()
        self.local_bus.publish(event_name, payload)
        if self.local_bus.last_error:
            self._status.status = "degraded"
            self._status.last_error = self.local_bus.last_error

    def get_status(self) -> EventBusStatus:
        return EventBusStatus(
            backend=self._status.backend,
            status=self._status.status,
            redis_enabled=self._status.redis_enabled,
            last_published_at=self._status.last_published_at,
            last_event_name=self._status.last_event_name,
            last_error=self._status.last_error,
        )


def _build_stream_map(settings: Settings) -> dict[str, str]:
    return {
        "news.created": settings.redis_stream_news_ingested,
        "news.created_batch": settings.redis_stream_news_ingested,
        "news.updated": settings.redis_stream_news_processed,
        "news.processed_batch": settings.redis_stream_news_processed,
        "news.signals_processed": settings.redis_stream_news_processed,
        "news.analysis_completed": settings.redis_stream_news_processed,
        "market.watchlist_refreshed": settings.redis_stream_market_watchlist,
    }


def build_event_bus(settings: Settings | None = None) -> HybridEventBus:
    settings = settings or get_settings()
    publisher_id = uuid4().hex
    redis_publisher = None
    if settings.event_bus_backend in {"hybrid", "redis"}:
        redis_publisher = RedisStreamPublisher(
            redis_url=settings.redis_url,
            maxlen=settings.redis_stream_maxlen,
            timeout_seconds=settings.event_bus_publish_timeout_seconds,
            publisher_id=publisher_id,
        )
    return HybridEventBus(
        backend=settings.event_bus_backend,
        redis_publisher=redis_publisher,
        stream_map=_build_stream_map(settings),
        publisher_id=publisher_id,
    )


_instance: HybridEventBus | None = None


def get_event_bus() -> HybridEventBus:
    global _instance
    if _instance is None:
        _instance = build_event_bus()
    return _instance


def set_event_bus(event_bus: HybridEventBus) -> None:
    global _instance
    _instance = event_bus
