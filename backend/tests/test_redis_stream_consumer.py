from __future__ import annotations

from app.core.config import Settings
from app.services.event_bus import HybridEventBus, InMemoryEventBus, _build_stream_map
from app.services.redis_stream_bus import RedisStreamConsumer, RedisStreamPublisher


class FakeRedis:
    """Minimal in-memory stand-in for redis-py stream commands used by publisher/consumer."""

    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._seq = 0

    def xadd(self, stream_name: str, message: dict[str, str], maxlen: int | None = None, approximate: bool = True) -> str:
        del maxlen, approximate
        self._seq += 1
        entry_id = f"{self._seq}-0"
        self.streams.setdefault(stream_name, []).append((entry_id, dict(message)))
        return entry_id

    def xread(self, streams: dict[str, str], count: int = 10, block: int = 0):
        del block
        result = []
        for stream_name, last_id in streams.items():
            entries = self.streams.get(stream_name, [])
            batch = []
            for entry_id, fields in entries:
                if last_id == "$":
                    continue
                if last_id == "0-0" or _id_greater(entry_id, last_id):
                    batch.append((entry_id, fields))
                    if len(batch) >= count:
                        break
            if batch:
                result.append((stream_name, batch))
        return result


def _id_greater(left: str, right: str) -> bool:
    if right in {"0", "0-0", "-"}:
        return True
    return left != right and left > right


def test_publisher_includes_event_name_and_publisher_id() -> None:
    fake = FakeRedis()
    publisher = RedisStreamPublisher(
        redis_url="redis://unused",
        maxlen=100,
        timeout_seconds=1.0,
        client=fake,  # type: ignore[arg-type]
        publisher_id="proc-a",
    )

    entry_id = publisher.publish("stream:news:ingested", {"id": 1}, event_name="news.created")

    assert entry_id == "1-0"
    _, fields = fake.streams["stream:news:ingested"][0]
    assert fields["event_name"] == "news.created"
    assert fields["publisher_id"] == "proc-a"
    assert '"id": 1' in fields["payload"] or '"id":1' in fields["payload"]


def test_consumer_injects_into_local_bus_without_republishing_to_redis() -> None:
    fake = FakeRedis()
    publisher = RedisStreamPublisher(
        redis_url="redis://unused",
        maxlen=100,
        timeout_seconds=1.0,
        client=fake,  # type: ignore[arg-type]
        publisher_id="scheduler",
    )
    local_bus = InMemoryEventBus()
    redis_publisher = RedisStreamPublisher(
        redis_url="redis://unused",
        maxlen=100,
        timeout_seconds=1.0,
        client=fake,  # type: ignore[arg-type]
        publisher_id="web",
    )
    bus = HybridEventBus(
        backend="hybrid",
        local_bus=local_bus,
        redis_publisher=redis_publisher,
        stream_map={"news.created": "stream:news:ingested"},
        publisher_id="web",
    )
    received: list[dict[str, object]] = []
    bus.subscribe("news.created", lambda payload: received.append(payload))

    publisher.publish("stream:news:ingested", {"id": 42, "title": "hi"}, event_name="news.created")
    before_count = len(fake.streams["stream:news:ingested"])

    consumer = RedisStreamConsumer(
        redis_url="redis://unused",
        streams=["stream:news:ingested"],
        inject=bus.inject_from_remote,
        client=fake,  # type: ignore[arg-type]
        publisher_id="web",
        initial_id="0-0",
    )
    consumed = consumer.poll_once(count=10)

    assert consumed == 1
    assert received == [{"id": 42, "title": "hi"}]
    assert len(fake.streams["stream:news:ingested"]) == before_count


def test_consumer_skips_messages_from_same_publisher() -> None:
    fake = FakeRedis()
    publisher = RedisStreamPublisher(
        redis_url="redis://unused",
        maxlen=100,
        timeout_seconds=1.0,
        client=fake,  # type: ignore[arg-type]
        publisher_id="web",
    )
    local_bus = InMemoryEventBus()
    bus = HybridEventBus(backend="memory", local_bus=local_bus, publisher_id="web")
    received: list[dict[str, object]] = []
    bus.subscribe("news.updated", lambda payload: received.append(payload))

    publisher.publish("stream:news:processed", {"id": 7}, event_name="news.updated")
    consumer = RedisStreamConsumer(
        redis_url="redis://unused",
        streams=["stream:news:processed"],
        inject=bus.inject_from_remote,
        client=fake,  # type: ignore[arg-type]
        publisher_id="web",
        initial_id="0-0",
    )

    assert consumer.poll_once() == 0
    assert received == []


def test_stream_map_includes_sse_events() -> None:
    settings = Settings()
    stream_map = _build_stream_map(settings)

    assert stream_map["news.created"] == settings.redis_stream_news_ingested
    assert stream_map["news.updated"] == settings.redis_stream_news_processed
    assert stream_map["news.created_batch"] == settings.redis_stream_news_ingested


def test_hybrid_publish_forwards_event_name_to_redis() -> None:
    fake = FakeRedis()
    redis_publisher = RedisStreamPublisher(
        redis_url="redis://unused",
        maxlen=100,
        timeout_seconds=1.0,
        client=fake,  # type: ignore[arg-type]
        publisher_id="scheduler",
    )
    bus = HybridEventBus(
        backend="hybrid",
        redis_publisher=redis_publisher,
        stream_map={"news.created": "stream:news:ingested"},
        publisher_id="scheduler",
    )

    bus.publish("news.created", {"id": 9})

    _, fields = fake.streams["stream:news:ingested"][0]
    assert fields["event_name"] == "news.created"
    assert fields["publisher_id"] == "scheduler"


def test_consumer_throttles_repeated_xread_error_logs(caplog) -> None:
    """redis 持续故障时,xread 异常日志按窗口降频(默认每 60s 最多一条),避免刷屏。"""
    import logging

    class AlwaysFailingRedis:
        def xread(self, streams, count: int = 10, block: int = 0):
            del streams, count, block
            raise RuntimeError("redis down")

    consumer = RedisStreamConsumer(
        redis_url="redis://unused",
        streams=["stream:news:ingested"],
        inject=lambda event_name, payload: None,
        client=AlwaysFailingRedis(),  # type: ignore[arg-type]
        error_log_interval_seconds=60.0,
    )

    with caplog.at_level(logging.ERROR, logger="app.services.redis_stream_bus"):
        for _ in range(5):
            assert consumer.poll_once() == 0

    error_logs = [record for record in caplog.records if "xread failed" in record.message]
    assert len(error_logs) == 1
