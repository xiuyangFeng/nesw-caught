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

# 批量发布时,投给 Redis 的总时间预算 = event_bus_publish_timeout_seconds * 该倍数。
# 预算耗尽后本批剩余事件只走内存总线(SSE 前端不受影响),避免"Redis 可达但慢"
# 时一批 50 条新闻在串行落库线程里最坏卡住 50 * socket_timeout 秒。
REDIS_BATCH_BUDGET_MULTIPLIER = 3.0
DEFAULT_REDIS_BATCH_BUDGET_SECONDS = 3.0


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
        # publish 会被多个 worker 线程并发调用,计数自增必须加锁(此前是裸 += ,
        # 在 CPython 下也不是原子操作,会丢计数)。
        self._counter_lock = threading.Lock()
        self.handler_error_count = 0

    def _incr_handler_error(self) -> None:
        with self._counter_lock:
            self.handler_error_count += 1

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
                self._incr_handler_error()


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
        redis_batch_budget_seconds: float = DEFAULT_REDIS_BATCH_BUDGET_SECONDS,
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
        self.redis_batch_budget_seconds = max(float(redis_batch_budget_seconds), 0.0)
        # 与 `_redis_consecutive_failures`(用于熔断,失败即清零)不同,这里是
        # 跨熔断周期的累计失败计数,专供可观测性上报使用。
        self.redis_publish_error_count = 0
        # `_status` / 熔断计数会被 scheduler、queue_worker、请求线程并发读写,
        # 此前完全无锁(读到撕裂状态、计数丢失)。这里用一把细粒度锁保护它们;
        # 锁内只做纯内存字段更新,绝不持锁做网络 I/O。
        self._state_lock = threading.Lock()
        self._status = EventBusStatus(
            backend=backend,
            status="ok",
            redis_enabled=backend in {"hybrid", "redis"} and redis_publisher is not None,
        )

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self.local_bus.subscribe(event_name, handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        self.local_bus.unsubscribe(event_name, handler)

    # ------------------------------------------------------------------ 内部

    def _mark_published(self, event_name: str) -> None:
        with self._state_lock:
            self._status.last_event_name = event_name
            self._status.last_published_at = _utc_now()

    def _publish_to_redis(self, event_name: str, payload: dict[str, Any]) -> tuple[bool, float]:
        """把单个事件发到 Redis。

        返回 ``(是否真的尝试了发布, 本次耗时秒数)``;后端未启用 Redis、事件没有
        映射到 stream、或熔断开启时返回 ``(False, 0.0)``。
        """
        if self.backend not in {"hybrid", "redis"} or self.redis_publisher is None:
            return False, 0.0
        stream_name = self.stream_map.get(event_name)
        if not stream_name:
            return False, 0.0

        with self._state_lock:
            circuit_open = self._clock() < self._redis_circuit_open_until
            if circuit_open:
                # 熔断开启:暂停 redis 发布,只走内存总线,避免每事件阻塞至 socket 超时。
                self._status.status = "degraded"
                self._status.last_error = self._status.last_error or "redis circuit open"
        if circuit_open:
            return False, 0.0

        started = self._clock()
        try:
            # 网络 I/O 刻意放在锁外执行。
            self.redis_publisher.publish(stream_name, payload, event_name=event_name)
        except Exception as exc:  # pragma: no cover - exercised via tests with fakes
            # 可恢复:redis 发布失败仍继续走内存总线(既有语义不变,
            # 见下方 self.local_bus.publish),这里补上累计计数(独立于
            # 熔断用的连续失败计数)使其可观测。
            with self._state_lock:
                self._redis_consecutive_failures += 1
                self.redis_publish_error_count += 1
                self._status.status = "degraded"
                self._status.last_error = str(exc)
                if self._redis_consecutive_failures >= self._circuit_breaker_threshold:
                    # 熔断冷却窗口;窗口过后下一次发布即半开重试。
                    self._redis_circuit_open_until = self._clock() + self._circuit_breaker_cooldown_seconds
                    self._redis_consecutive_failures = 0
        else:
            with self._state_lock:
                self._redis_consecutive_failures = 0
                self._status.status = "ok"
                self._status.last_error = None
        return True, max(self._clock() - started, 0.0)

    def _publish_local(self, event_name: str, payload: dict[str, Any]) -> None:
        self.local_bus.publish(event_name, payload)
        if self.local_bus.last_error:
            with self._state_lock:
                self._status.status = "degraded"
                self._status.last_error = self.local_bus.last_error

    # ------------------------------------------------------------------ 对外

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        self._mark_published(event_name)
        self._publish_to_redis(event_name, payload)
        self._publish_local(event_name, payload)

    def publish_batch(
        self,
        event_name: str,
        payloads: list[dict[str, Any]],
        *,
        redis_budget_seconds: float | None = None,
    ) -> int:
        """批量发布同名事件,并对 Redis 这一跳施加整体时间预算。

        内存总线(SSE 前端依赖的 `news.created` 逐条推送)始终逐条投递,语义不变;
        只有 Redis 这一跳在累计耗时超预算后跳过本批剩余事件——"Redis 可达但慢"
        既不会触发按连续失败计数的熔断,又会把串行落库线程卡住 N * socket_timeout 秒。

        返回实际投递到 Redis 的事件条数(便于观测降级发生的程度)。
        """
        if not payloads:
            return 0
        budget = self.redis_batch_budget_seconds if redis_budget_seconds is None else float(redis_budget_seconds)
        spent = 0.0
        redis_published = 0
        degraded_from: int | None = None
        for index, payload in enumerate(payloads):
            self._mark_published(event_name)
            if budget <= 0 or spent < budget:
                attempted, elapsed = self._publish_to_redis(event_name, payload)
                if attempted:
                    redis_published += 1
                spent += elapsed
            elif degraded_from is None:
                degraded_from = index
            self._publish_local(event_name, payload)

        if degraded_from is not None:
            with self._state_lock:
                self._status.status = "degraded"
                self._status.last_error = (
                    f"redis publish budget exhausted after {degraded_from} of {len(payloads)} "
                    f"'{event_name}' events ({spent:.2f}s > {budget:.2f}s); remainder local-only"
                )
        return redis_published

    def inject_from_remote(self, event_name: str, payload: dict[str, Any]) -> None:
        """Inject a cross-process event into local subscribers only (no Redis echo)."""
        self._mark_published(event_name)
        self._publish_local(event_name, payload)

    def get_status(self) -> EventBusStatus:
        with self._state_lock:
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
        redis_batch_budget_seconds=settings.event_bus_publish_timeout_seconds * REDIS_BATCH_BUDGET_MULTIPLIER,
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
