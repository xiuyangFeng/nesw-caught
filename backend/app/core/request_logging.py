"""请求级日志中间件：request_id 生成/透传 + HTTP 访问日志。

刻意用纯 ASGI 中间件而非 Starlette BaseHTTPMiddleware：后者会把下游包进
独立任务并代理响应流，对本项目的 SSE 长连接（/api/stream）有缓冲与取消
语义上的坑；纯 ASGI 在同一任务里调用下游，contextvars 直接生效。

- 入站若带 X-Request-ID（经 sanitize 校验）则沿用，便于与上游网关串联；
  否则生成 16 位 hex。响应头始终回写 X-Request-ID。
- 访问日志 logger 名为 "app.access"：method path status duration_ms client。
  命中排除前缀（默认健康检查与 SSE 长连接）时只透传 request_id 不记访问行。
- 5xx 记 warning，其余记 info；下游抛出的未捕获异常记一条 500 访问行后原样
  上抛（堆栈由 FastAPI/uvicorn 的异常处理链负责，这里不重复打）。
"""
from __future__ import annotations

import logging
import time
from urllib.parse import parse_qsl, urlencode

from app.core.log_context import (
    get_request_id,
    get_task_id,
    new_request_id,
    request_id_var,
    sanitize_request_id,
)

access_logger = logging.getLogger("app.access")

_REQUEST_ID_HEADER = b"x-request-id"
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "app_token",
    "authorization",
    "token",
}


class RequestLoggingMiddleware:
    def __init__(self, app, *, access_log_enabled: bool = True, exclude_prefixes: tuple[str, ...] = ()) -> None:
        self.app = app
        self.access_log_enabled = access_log_enabled
        self.exclude_prefixes = exclude_prefixes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == _REQUEST_ID_HEADER:
                incoming = sanitize_request_id(value.decode("latin-1"))
                break
        request_id = incoming or new_request_id()

        path = scope.get("path", "")
        should_log = self.access_log_enabled and not any(
            path.startswith(prefix) for prefix in self.exclude_prefixes
        )

        status_holder = {"status": None}

        async def send_with_request_id(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _REQUEST_ID_HEADER
                ]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            if should_log:
                self._log_access(scope, 500, started)
            raise
        else:
            if should_log:
                self._log_access(scope, status_holder["status"], started)
        finally:
            request_id_var.reset(token)

    def _log_access(self, scope, status, started: float) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        client = scope.get("client")
        client_host = client[0] if client else "-"
        query = scope.get("query_string", b"")
        target = scope.get("path", "")
        if query:
            query_pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=True)
            safe_query = urlencode([
                (key, "***" if key.lower() in _SENSITIVE_QUERY_KEYS else value)
                for key, value in query_pairs
            ])
            if safe_query:
                target = f"{target}?{safe_query}"
        level = logging.WARNING if (status or 500) >= 500 else logging.INFO
        request_id = get_request_id()
        task_id = get_task_id()
        context_parts = []
        if request_id:
            context_parts.append(f"req={request_id}")
        if task_id:
            context_parts.append(f"task={task_id}")
        access_logger.log(
            level,
            "%s %s %s %.1fms client=%s",
            scope.get("method", "-"),
            target,
            status if status is not None else "-",
            duration_ms,
            client_host,
            extra={
                "request_id": request_id,
                "task_id": task_id,
                "log_ctx": f" [{' '.join(context_parts)}]" if context_parts else "",
            },
        )
