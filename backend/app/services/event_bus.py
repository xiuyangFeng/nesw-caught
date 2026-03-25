from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.services.redis_stream_bus import RedisStreamPublisher

EventHandler = Callable[[dict[str, Any]], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        for handler in self._handlers[event_name]:
            handler(payload)


class HybridEventBus:
    def __init__(
        self,
        *,
        backend: str,
        local_bus: InMemoryEventBus | None = None,
        redis_publisher: RedisStreamPublisher | Any | None = None,
        stream_map: dict[str, str] | None = None,
    ) -> None:
        self.backend = backend
        self.local_bus = local_bus or InMemoryEventBus()
        self.redis_publisher = redis_publisher
        self.stream_map = stream_map or {}
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
                    self.redis_publisher.publish(stream_name, payload)
                    self._status.status = "ok"
                    self._status.last_error = None
                except Exception as exc:  # pragma: no cover - exercised via tests with fakes
                    self._status.status = "degraded"
                    self._status.last_error = str(exc)

        self.local_bus.publish(event_name, payload)

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
        "news.created_batch": settings.redis_stream_news_ingested,
        "news.processed_batch": settings.redis_stream_news_processed,
        "news.signals_processed": settings.redis_stream_news_processed,
        "news.analysis_completed": settings.redis_stream_news_processed,
        "market.watchlist_refreshed": settings.redis_stream_market_watchlist,
    }


def build_event_bus(settings: Settings | None = None) -> HybridEventBus:
    settings = settings or get_settings()
    redis_publisher = None
    if settings.event_bus_backend in {"hybrid", "redis"}:
        redis_publisher = RedisStreamPublisher(
            redis_url=settings.redis_url,
            maxlen=settings.redis_stream_maxlen,
            timeout_seconds=settings.event_bus_publish_timeout_seconds,
        )
    return HybridEventBus(
        backend=settings.event_bus_backend,
        redis_publisher=redis_publisher,
        stream_map=_build_stream_map(settings),
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
