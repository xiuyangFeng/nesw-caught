"""日志上下文透传：request_id / task_id 经 contextvars 跨调用链传递。

- HTTP 请求：RequestLoggingMiddleware（core/request_logging.py）在请求入口
  bind_request_id()，同一请求内所有日志（含 anyio 线程池里跑的同步路由，
  contextvars 会随任务拷贝传播）自动携带该 id。
- 后台 worker：BaseWorker 每个周期 bind_task_id("{worker_name}#{seq}")，
  同一周期内的日志可互相串联。

字段由 configure_logging 挂在 handler 上的 LogContextFilter 注入 LogRecord：
json 格式输出 request_id/task_id 字段，plain 格式经 %(log_ctx)s 追加
" [req=..]" / " [task=..]" 后缀，无上下文时为空串，对第三方库日志同样生效。
"""
from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("log_request_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("log_task_id", default=None)

# 透传外部传入的 X-Request-ID 时的清洗上限：防止恶意超长/控制字符注入日志。
_MAX_REQUEST_ID_LENGTH = 64


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def sanitize_request_id(raw: str | None) -> str | None:
    """外部传入的 request id 只接受短小的可打印安全字符，否则视为无效。"""
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate or len(candidate) > _MAX_REQUEST_ID_LENGTH:
        return None
    if not all(ch.isalnum() or ch in "-_." for ch in candidate):
        return None
    return candidate


def get_request_id() -> str | None:
    return request_id_var.get()


def get_task_id() -> str | None:
    return task_id_var.get()


@contextmanager
def bind_request_id(request_id: str):
    token = request_id_var.set(request_id)
    try:
        yield request_id
    finally:
        request_id_var.reset(token)


@contextmanager
def bind_task_id(task_id: str):
    token = task_id_var.set(task_id)
    try:
        yield task_id
    finally:
        task_id_var.reset(token)


class LogContextFilter(logging.Filter):
    """把 contextvars 里的上下文写进 LogRecord。

    以 Filter 形式挂在 handler 上（而非 Formatter 子类），plain/json 两种
    formatter 与第三方库的 record 都能拿到字段；永远返回 True，不做过滤。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        task_id = task_id_var.get()
        record.request_id = request_id
        record.task_id = task_id
        parts = []
        if request_id:
            parts.append(f"req={request_id}")
        if task_id:
            parts.append(f"task={task_id}")
        record.log_ctx = f" [{' '.join(parts)}]" if parts else ""
        return True
