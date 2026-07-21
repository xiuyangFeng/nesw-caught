from __future__ import annotations

import threading
import time
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
    # 可观测性:被吞掉的异常累计计数(进程内),供 /ops 等只读消费方及
    # BackgroundQueueWorker 的周期性回写使用;默认 0 保持向后兼容。
    local_handler_error_count: int = 0
    redis_publish_error_count: int = 0


class InMemoryEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        # `_handlers` 会被请求线程(SSE 连接的 subscribe/unsubscribe)与 worker
        # 线程(publish)并发读写,用这把锁保护它的全部修改,避免边迭代边改。
        self._handlers_lock = threading.Lock()
        self.last_error: str | None = None
        # 可观测性:单个订阅者失败不应影响其他订阅者(既有语义不变),但历史上
        # 吞掉的异常完全不可数。这里只加一个累计计数,由 HybridEventBus.get_status()
        # 透出,再由 BackgroundQueueWorker 周期性回写到既有 worker_runtime_status 表。
        self.handler_error_count = 0

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._handlers_lock:
            self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._handlers_lock:
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
        # 锁内只取快照,锁外再调用 handler:避免持锁调用 handler(handler 内部
        # 再次 subscribe/unsubscribe 会重入同一把锁造成死锁),也避免跨线程
        # 边迭代边改这一原始列表对象。
        with self._handlers_lock:
            handlers_snapshot = list(self._handlers[event_name])
        for handler in handlers_snapshot:
            try:
                handler(payload)
            except Exception as exc:
                # 可恢复:单个订阅者失败不影响其他订阅者继续消费同一事件(既有语义
                # 不变),这里只补上累计计数使其可观测。
                handler_name = getattr(handler, "__name__", str(handler))
                logger.exception(
                    f"EventBus handler '{handler_name}' failed on event '{event_name}'"
                )
                self.last_error = f"Handler '{handler_name}' failed on event '{event_name}': {exc}"
                self.handler_error_count += 1


class HybridEventBus:
    def __init__(
        self,
        *,
        backend: str,
        local_bus: InMemoryEventBus | None = None,
        redis_publisher: RedisStreamPublisher | Any | None = None,
        stream_map: dict[str, str] | None = None,
        publisher_id: str | None = None,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.backend = backend
        self.local_bus = local_bus or InMemoryEventBus()
        self.redis_publisher = redis_publisher
        self.stream_map = stream_map or {}
        self.publisher_id = publisher_id or getattr(redis_publisher, "publisher_id", None) or uuid4().hex
        if redis_publisher is not None and getattr(redis_publisher, "publisher_id", None) is None:
            redis_publisher.publisher_id = self.publisher_id
        # redis 发布熔断:连续失败 threshold 次后暂停发布 cooldown 秒,期间只走内存总线。
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_cooldown_seconds = circuit_breaker_cooldown_seconds
        self._clock = clock
        self._redis_consecutive_failures = 0
        self._redis_circuit_open_until = 0.0
        # 与 `_redis_consecutive_failures`(用于熔断,失败即清零)不同,这里是
        # 跨熔断周期的累计失败计数,专供可观测性上报使用。
        self.redis_publish_error_count = 0
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
                if self._clock() < self._redis_circuit_open_until:
                    # 熔断开启:暂停 redis 发布,只走内存总线,避免每事件阻塞至 socket 超时。
                    self._status.status = "degraded"
                    self._status.last_error = self._status.last_error or "redis circuit open"
                else:
                    try:
                        self.redis_publisher.publish(stream_name, payload, event_name=event_name)
                        self._redis_consecutive_failures = 0
                        self._status.status = "ok"
                        self._status.last_error = None
                    except Exception as exc:  # pragma: no cover - exercised via tests with fakes
                        # 可恢复:redis 发布失败仍继续走内存总线(既有语义不变,
                        # 见下方 self.local_bus.publish),这里补上累计计数(独立于
                        # 熔断用的连续失败计数)使其可观测。
                        self._redis_consecutive_failures += 1
                        self.redis_publish_error_count += 1
                        self._status.status = "degraded"
                        self._status.last_error = str(exc)
                        if self._redis_consecutive_failures >= self._circuit_breaker_threshold:
                            # 熔断冷却窗口;窗口过后下一次发布即半开重试。
                            self._redis_circuit_open_until = self._clock() + self._circuit_breaker_cooldown_seconds
                            self._redis_consecutive_failures = 0

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
            local_handler_error_count=self.local_bus.handler_error_count,
            redis_publish_error_count=self.redis_publish_error_count,
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
