import asyncio
import threading

from fastapi.testclient import TestClient

from app.api.routes import stream as stream_route
from app.core import auth
from app.core.config import Settings
from app.main import app


class FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


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

    response = asyncio.run(stream_route.stream_events(FakeRequest(), limit=2))
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

    response = asyncio.run(stream_route.stream_events(FakeRequest(), limit=2))

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(_collect_body())

    assert body.count('"type":"stream.keepalive"') == 2


def _enforce_auth(monkeypatch, token: str = "test-app-token-secret") -> str:
    # 覆盖测试套件默认关闭的鉴权开关（conftest 设置 VERIFY_APP_TOKEN=false），
    # 并固定本机 App Token
    enforced = Settings(verify_app_token=True)
    monkeypatch.setattr(auth, "get_settings", lambda: enforced)
    monkeypatch.setattr(auth, "_app_token", token)
    return token


def test_stream_events_returns_401_without_token_when_auth_enforced(monkeypatch) -> None:
    _enforce_auth(monkeypatch)
    client = TestClient(app)

    response = client.get("/api/stream/events", params={"limit": 1})

    assert response.status_code == 401


def test_stream_events_returns_401_with_wrong_query_token(monkeypatch) -> None:
    _enforce_auth(monkeypatch)
    client = TestClient(app)

    response = client.get("/api/stream/events", params={"limit": 1, "token": "wrong-token"})

    assert response.status_code == 401


def test_stream_events_connects_with_valid_query_token(monkeypatch) -> None:
    token = _enforce_auth(monkeypatch)
    # 缩短 keepalive 周期，让 limit=1 的流快速结束
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)
    client = TestClient(app)

    with client.stream(
        "GET", "/api/stream/events", params={"limit": 1, "token": token}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(chunk for chunk in response.iter_text())

    assert '"type":"stream.keepalive"' in body


def test_non_stream_routes_still_reject_query_token(monkeypatch) -> None:
    # query token 只对 SSE 流路由生效，其他路由仍必须使用请求头
    token = _enforce_auth(monkeypatch)
    client = TestClient(app)

    response = client.get("/api/news", params={"token": token})

    assert response.status_code == 401
