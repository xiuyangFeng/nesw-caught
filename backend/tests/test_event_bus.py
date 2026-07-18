from app.core.config import Settings
from app.services.event_bus import HybridEventBus, InMemoryEventBus


class DummyRedisPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.event_names: list[str | None] = []

    def publish(self, stream_name: str, payload: dict[str, object], *, event_name: str | None = None) -> str:
        self.calls.append((stream_name, payload))
        self.event_names.append(event_name)
        return "1-0"


class FailingRedisPublisher:
    def publish(self, stream_name: str, payload: dict[str, object], *, event_name: str | None = None) -> str:
        del stream_name, payload, event_name
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


class CountingFailingRedisPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish(self, stream_name: str, payload: dict[str, object], *, event_name: str | None = None) -> str:
        del stream_name, payload, event_name
        self.calls += 1
        raise RuntimeError("redis unavailable")


def test_redis_circuit_breaker_skips_redis_after_repeated_failures_and_recovers() -> None:
    """连续失败达到阈值后熔断:暂停 redis 发布(只走内存总线),冷却窗口过后半开重试。"""
    now = [1000.0]
    publisher = CountingFailingRedisPublisher()
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(
        backend="hybrid",
        local_bus=local_bus,
        redis_publisher=publisher,
        stream_map={"news.created": "stream:news:ingested"},
        circuit_breaker_threshold=3,
        circuit_breaker_cooldown_seconds=60.0,
        clock=lambda: now[0],
    )
    received: list[dict[str, object]] = []
    bus.subscribe("news.created", lambda payload: received.append(payload))

    for _ in range(3):
        bus.publish("news.created", {"id": 1})
    assert publisher.calls == 3

    # 熔断已开启:第 4 次发布不再触碰 redis,本地订阅者照常收到。
    bus.publish("news.created", {"id": 2})
    assert publisher.calls == 3
    assert len(received) == 4
    assert bus.get_status().status == "degraded"

    # 冷却窗口内继续短路。
    now[0] += 30.0
    bus.publish("news.created", {"id": 3})
    assert publisher.calls == 3

    # 冷却窗口过后半开重试:再次调用 redis(失败后重新计次)。
    now[0] += 31.0
    bus.publish("news.created", {"id": 4})
    assert publisher.calls == 4
    assert len(received) == 6


def test_redis_circuit_breaker_does_not_open_below_threshold() -> None:
    now = [1000.0]
    publisher = CountingFailingRedisPublisher()
    bus = HybridEventBus(
        backend="hybrid",
        local_bus=InMemoryEventBus(),
        redis_publisher=publisher,
        stream_map={"news.created": "stream:news:ingested"},
        circuit_breaker_threshold=3,
        circuit_breaker_cooldown_seconds=60.0,
        clock=lambda: now[0],
    )

    bus.publish("news.created", {"id": 1})
    bus.publish("news.created", {"id": 2})

    # 未达阈值:每次都仍尝试 redis。
    assert publisher.calls == 2
    assert bus.get_status().status == "degraded"
