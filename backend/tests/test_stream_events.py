import asyncio
import threading

from app.api.routes import stream as stream_route


def test_stream_events_forwards_news_created_and_news_updated(monkeypatch) -> None:
    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}
            self.ready = threading.Event()

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)
            if all(name in self.handlers for name in ("news.created", "news.updated")):
                self.ready.set()

        def unsubscribe(self, event_name: str, handler) -> None:
            handlers = self.handlers.get(event_name, [])
            self.handlers[event_name] = [item for item in handlers if item is not handler]

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    fake_bus = FakeBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: fake_bus)

    response = stream_route.stream_events(limit=2)
    publisher = threading.Thread(
        target=lambda: (
            fake_bus.ready.wait(2),
            fake_bus.publish("news.created", {"id": 1, "title": "created"}),
            fake_bus.publish("news.updated", {"id": 1, "title": "updated", "updated_fields": ["sentiment_label"]}),
        ),
        daemon=True,
    )
    publisher.start()

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(_collect_body())
    publisher.join(timeout=1)

    assert '"type":"news.created"' in body
    assert '"type":"news.updated"' in body
    assert '"payload":{"id":1,"title":"created"}' in body
    assert '"payload":{"id":1,"title":"updated","updated_fields":["sentiment_label"]}' in body


def test_stream_events_keeps_emitting_keepalive_when_idle(monkeypatch) -> None:
    class FakeBus:
        def subscribe(self, event_name: str, handler) -> None:
            del event_name, handler

        def unsubscribe(self, event_name: str, handler) -> None:
            del event_name, handler

    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: FakeBus())

    response = stream_route.stream_events(limit=2)

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(_collect_body())

    assert body.count('"type":"stream.keepalive"') == 2
