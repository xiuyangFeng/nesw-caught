"""Observability tests for optimization-plan.md #12: `InMemoryEventBus.publish`
and `HybridEventBus.publish` both catch broad `except Exception` around a
single subscriber/redis-publish call so one failure doesn't take down the rest
of the batch (existing semantics, unchanged). This file verifies the swallowed
failures are now counted and exposed via `get_status()`.
"""

from __future__ import annotations

from app.services.event_bus import HybridEventBus, InMemoryEventBus


class FailingRedisPublisher:
    def publish(self, stream_name: str, payload: dict[str, object], *, event_name: str | None = None) -> str:
        del stream_name, payload, event_name
        raise RuntimeError("redis unavailable")


def test_local_handler_failure_increments_handler_error_count() -> None:
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(backend="memory", local_bus=local_bus)

    calls: list[dict[str, object]] = []

    def failing_handler(payload: dict[str, object]) -> None:
        raise ValueError("failing handler error")

    def normal_handler(payload: dict[str, object]) -> None:
        calls.append(payload)

    bus.subscribe("test_event", failing_handler)
    bus.subscribe("test_event", normal_handler)

    # Publish should not raise, and the other subscriber must still run.
    bus.publish("test_event", {"data": "test"})
    assert calls == [{"data": "test"}]

    status = bus.get_status()
    assert status.status == "degraded"
    assert status.local_handler_error_count == 1

    # A second failure on a different event must keep accumulating.
    bus.subscribe("other_event", failing_handler)
    bus.publish("other_event", {"data": "again"})
    assert bus.get_status().local_handler_error_count == 2


def test_redis_publish_failure_increments_error_count_and_still_falls_back_locally() -> None:
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(
        backend="hybrid",
        local_bus=local_bus,
        redis_publisher=FailingRedisPublisher(),
        stream_map={"news.created_batch": "stream:news:ingested"},
    )
    received: list[dict[str, object]] = []
    bus.subscribe("news.created_batch", lambda payload: received.append(payload))

    bus.publish("news.created_batch", {"news_ids": [9]})

    # Existing fallback semantics: local subscribers still run despite the
    # redis publish failure.
    assert received == [{"news_ids": [9]}]

    status = bus.get_status()
    assert status.status == "degraded"
    assert status.last_error == "redis unavailable"
    assert status.redis_publish_error_count == 1

    bus.publish("news.created_batch", {"news_ids": [10]})
    assert bus.get_status().redis_publish_error_count == 2
