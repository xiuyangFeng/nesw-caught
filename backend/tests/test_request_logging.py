"""RequestLoggingMiddleware（request_id 透传 + 访问日志）的行为测试。

用最小 FastAPI app 而非全量 app.main:app：中间件行为与业务路由无关，
小 app 不依赖数据库初始化，失败时定位也更直接。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.log_context import get_request_id, sanitize_request_id
from app.core.request_logging import RequestLoggingMiddleware


def _build_client(**middleware_kwargs) -> TestClient:
    app = FastAPI()

    @app.get("/ok")
    def ok() -> dict:
        return {"request_id_in_handler": get_request_id()}

    @app.get("/excluded/ping")
    def excluded() -> dict:
        return {"request_id_in_handler": get_request_id()}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaput")

    app.add_middleware(RequestLoggingMiddleware, **middleware_kwargs)
    return TestClient(app, raise_server_exceptions=False)


def test_generates_request_id_and_echoes_response_header():
    client = _build_client()
    response = client.get("/ok")

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert request_id
    # 路由处理函数内 contextvar 已绑定同一个 id
    assert response.json()["request_id_in_handler"] == request_id


def test_reuses_valid_incoming_request_id():
    client = _build_client()
    response = client.get("/ok", headers={"X-Request-ID": "gw-upstream-42"})
    assert response.headers["x-request-id"] == "gw-upstream-42"
    assert response.json()["request_id_in_handler"] == "gw-upstream-42"


def test_rejects_malformed_incoming_request_id():
    client = _build_client()
    response = client.get("/ok", headers={"X-Request-ID": "bad id\nwith junk"})
    generated = response.headers["x-request-id"]
    assert generated != "bad id\nwith junk"
    assert generated  # 换成了服务端生成的安全 id


def test_sanitize_request_id_rules():
    assert sanitize_request_id("abc-123_X.9") == "abc-123_X.9"
    assert sanitize_request_id("  spaced  ") == "spaced"
    assert sanitize_request_id("") is None
    assert sanitize_request_id(None) is None
    assert sanitize_request_id("x" * 65) is None
    assert sanitize_request_id("has space") is None


def test_access_log_line_emitted(caplog):
    client = _build_client()
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/ok?q=1")

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "GET /ok?q=1 200" in message
    assert "ms client=" in message
    assert records[0].levelno == logging.INFO
    assert records[0].request_id == response.headers["x-request-id"]


def test_access_log_redacts_sensitive_query_values(caplog):
    client = _build_client()
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/ok?token=top-secret&api_key=also-secret&q=visible")

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "top-secret" not in message
    assert "also-secret" not in message
    assert "token=%2A%2A%2A" in message
    assert "api_key=%2A%2A%2A" in message
    assert "q=visible" in message


def test_excluded_prefix_skips_access_log_but_keeps_request_id(caplog):
    client = _build_client(exclude_prefixes=("/excluded",))
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/excluded/ping")

    assert response.headers["x-request-id"]
    assert response.json()["request_id_in_handler"] == response.headers["x-request-id"]
    assert not [r for r in caplog.records if r.name == "app.access"]


def test_access_log_disabled_globally(caplog):
    client = _build_client(access_log_enabled=False)
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/ok")

    assert response.headers["x-request-id"]
    assert not [r for r in caplog.records if r.name == "app.access"]


def test_unhandled_exception_logs_500_at_warning(caplog):
    client = _build_client()
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/boom")

    assert response.status_code == 500
    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    assert "GET /boom 500" in records[0].getMessage()
    assert records[0].levelno == logging.WARNING


def test_context_is_reset_between_requests():
    client = _build_client()
    client.get("/ok")
    # 请求结束后当前上下文不残留 request_id
    assert get_request_id() is None
