from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import app.services.feishu_client as feishu_client


@dataclass
class _FakeResponse:
    payload: dict[str, Any]
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


def _make_fake_httpx_client(
    *,
    token_responses: list[dict[str, Any]],
    message_responses: list[dict[str, Any]],
) -> type:
    token_queue = list(token_responses)
    message_queue = list(message_responses)

    class _FakeHttpxClient:
        instances: list[_FakeHttpxClient] = []
        posts: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = []

        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout
            self.closed = False
            self.instance_posts: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = []
            self.__class__.instances.append(self)

        def __enter__(self) -> _FakeHttpxClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.closed = True

        def post(
            self,
            url: str,
            *,
            json: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
        ):
            record = (url, json, params)
            self.__class__.posts.append(record)
            self.instance_posts.append(record)
            if url.endswith("/tenant_access_token/internal"):
                payload = token_queue.pop(0) if token_queue else token_responses[-1]
                return _FakeResponse(payload)

            payload = message_queue.pop(0) if message_queue else message_responses[-1]
            return _FakeResponse(payload)

    _FakeHttpxClient.__name__ = "FakeHttpxClient"
    _FakeHttpxClient.instances = []
    _FakeHttpxClient.posts = []
    return _FakeHttpxClient


@pytest.fixture(autouse=True)
def _reset_fake_httpx_client() -> None:
    shared_sender_helper = getattr(feishu_client, "get_shared_feishu_sender", None)
    if shared_sender_helper is not None and hasattr(shared_sender_helper, "cache_clear"):
        shared_sender_helper.cache_clear()
    yield
    if shared_sender_helper is not None and hasattr(shared_sender_helper, "cache_clear"):
        shared_sender_helper.cache_clear()


def test_get_shared_feishu_sender_reuses_instance_and_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _make_fake_httpx_client(
        token_responses=[{"code": 0, "tenant_access_token": "token-1", "expire": 3600}],
        message_responses=[{"code": 0, "msg": "ok"}, {"code": 0, "msg": "ok"}],
    )
    monkeypatch.setattr(feishu_client.httpx, "Client", fake_client)

    helper = getattr(feishu_client, "get_shared_feishu_sender", None)
    assert helper is not None

    client = helper(app_id="cli_test123", app_secret="secret_abc")
    same_client = helper(app_id="cli_test123", app_secret="secret_abc")
    card = {"header": {"title": {"content": "hello"}}}

    client.send_card(target_type="chat", target_id="oc_test_chat_id", card=card)
    same_client.send_card(target_type="chat", target_id="oc_test_chat_id", card=card)

    assert client is same_client
    assert len(fake_client.instances) == 1
    assert len([item for item in fake_client.posts if item[0].endswith("/tenant_access_token/internal")]) == 1
    assert len([item for item in fake_client.posts if item[0].endswith("/im/v1/messages")]) == 2


def test_feishu_client_refreshes_token_once_after_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _make_fake_httpx_client(
        token_responses=[
            {"code": 0, "tenant_access_token": "token-1", "expire": 3600},
            {"code": 0, "tenant_access_token": "token-2", "expire": 3600},
        ],
        message_responses=[
            {"code": 99991663, "msg": "invalid tenant_access_token"},
            {"code": 0, "msg": "ok"},
        ],
    )
    monkeypatch.setattr(feishu_client.httpx, "Client", fake_client)

    client = feishu_client.FeishuClient(app_id="cli_test123", app_secret="secret_abc")
    card = {"header": {"title": {"content": "hello"}}}

    result = client.send_card(target_type="chat", target_id="oc_test_chat_id", card=card)

    assert result["code"] == 0
    assert len([item for item in fake_client.posts if item[0].endswith("/tenant_access_token/internal")]) == 2
    assert len([item for item in fake_client.posts if item[0].endswith("/im/v1/messages")]) == 2


def test_feishu_error_classifier_marks_invalid_token_retryable_and_config_errors_non_retryable() -> None:
    classifier = getattr(feishu_client, "classify_feishu_error", None)
    assert classifier is not None

    invalid_token = classifier({"code": 99991663, "msg": "invalid tenant_access_token"})
    assert invalid_token.retryable is True
    assert invalid_token.refresh_token is True

    config_error = classifier({"code": 40004, "msg": "app_secret invalid"})
    assert config_error.retryable is False
    assert config_error.refresh_token is False
