from app.core.config import Settings
from app.services.event_bus import HybridEventBus, InMemoryEventBus


class DummyRedisPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def publish(self, stream_name: str, payload: dict[str, object]) -> str:
        self.calls.append((stream_name, payload))
        return "1-0"


class FailingRedisPublisher:
    def publish(self, stream_name: str, payload: dict[str, object]) -> str:
        del stream_name, payload
        raise RuntimeError("redis unavailable")


def test_hybrid_event_bus_publishes_to_redis_and_local_subscribers() -> None:
    publisher = DummyRedisPublisher()
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(
        backend="hybrid",
        local_bus=local_bus,
        redis_publisher=publisher,
        stream_map={"news.created_batch": "stream:news:ingested"},
    )
    received: list[dict[str, object]] = []
    bus.subscribe("news.created_batch", lambda payload: received.append(payload))

    bus.publish("news.created_batch", {"news_ids": [1, 2, 3]})

    assert received == [{"news_ids": [1, 2, 3]}]
    assert publisher.calls == [("stream:news:ingested", {"news_ids": [1, 2, 3]})]
    status = bus.get_status()
    assert status.backend == "hybrid"
    assert status.status == "ok"
    assert status.last_error is None
    assert status.last_event_name == "news.created_batch"


def test_hybrid_event_bus_falls_back_to_local_subscribers_when_redis_publish_fails() -> None:
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

    assert received == [{"news_ids": [9]}]
    status = bus.get_status()
    assert status.backend == "hybrid"
    assert status.status == "degraded"
    assert status.last_error == "redis unavailable"


def test_memory_event_bus_skips_redis_publish() -> None:
    publisher = DummyRedisPublisher()
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(
        backend="memory",
        local_bus=local_bus,
        redis_publisher=publisher,
        stream_map={"news.created_batch": "stream:news:ingested"},
    )
    received: list[dict[str, object]] = []
    bus.subscribe("news.created_batch", lambda payload: received.append(payload))

    bus.publish("news.created_batch", {"news_ids": [5]})

    assert received == [{"news_ids": [5]}]
    assert publisher.calls == []
    status = bus.get_status()
    assert status.backend == "memory"
    assert status.status == "ok"


def test_settings_expose_redis_event_layer_defaults() -> None:
    settings = Settings()

    assert settings.event_bus_backend == "hybrid"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.redis_stream_news_ingested == "stream:news:ingested"
    assert settings.redis_stream_news_processed == "stream:news:processed"
    assert settings.redis_stream_maxlen == 1000
    assert settings.event_bus_publish_timeout_seconds == 1.0
    assert settings.market_quote_producer_enabled is True
    assert settings.market_quote_poll_interval_seconds == 15.0


def test_local_event_handler_exception_isolation() -> None:
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(backend="memory", local_bus=local_bus)

    calls = []

    def failing_handler(payload):
        raise ValueError("failing handler error")

    def normal_handler(payload):
        calls.append(payload)

    bus.subscribe("test_event", failing_handler)
    bus.subscribe("test_event", normal_handler)

    # Publish should not raise exception
    bus.publish("test_event", {"data": "test"})

    # The normal handler should still run
    assert calls == [{"data": "test"}]

    # Status should be degraded with the error registered
    status = bus.get_status()
    assert status.status == "degraded"
    assert "failing handler error" in str(status.last_error)
