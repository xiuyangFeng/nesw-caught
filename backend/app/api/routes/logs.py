"""前端错误日志上报端点。

前端 utils/logger.ts 批量上报 warn/error 级日志，落入后端统一日志流
（logger 名 "frontend"），与后端日志共用输出/轮转/格式配置，排查用户端
问题时可直接在 backend.log 里按 request_id 或时间线检索。

防滥用三层：批大小上限（超出整批 413）、单条字段截断、进程级滑动窗口
限流（超出的条目静默丢弃并计入 dropped，返回 200 —— 前端上报是尽力而为
的旁路信号，不该因限流让前端收到报错再触发新一轮上报）。
"""
import logging
import time
from collections import deque
from threading import Lock

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.frontend_log import FrontendLogBatch, FrontendLogIngestResult

router = APIRouter()

frontend_logger = logging.getLogger("frontend")

_LEVEL_MAP = {"warn": logging.WARNING, "error": logging.ERROR}

# 滑动窗口限流状态（进程级）。deque 存每条已接受日志的单调时钟时间戳。
_rate_lock = Lock()
_accepted_at: deque[float] = deque()
_RATE_WINDOW_SECONDS = 60.0


def _try_acquire_rate_slots(count: int, limit: int) -> int:
    """返回获准写入的条数（0..count），超窗口的旧记录顺带清退。"""
    now = time.monotonic()
    with _rate_lock:
        while _accepted_at and now - _accepted_at[0] > _RATE_WINDOW_SECONDS:
            _accepted_at.popleft()
        granted = max(0, min(count, limit - len(_accepted_at)))
        for _ in range(granted):
            _accepted_at.append(now)
        return granted


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[:limit] + "…(truncated)"


@router.post("/frontend", response_model=FrontendLogIngestResult)
def ingest_frontend_logs(batch: FrontendLogBatch) -> FrontendLogIngestResult:
    settings = get_settings()
    if not settings.frontend_log_enabled:
        return FrontendLogIngestResult(accepted=0, dropped=len(batch.entries))
    if len(batch.entries) > settings.frontend_log_max_entries_per_request:
        raise HTTPException(status_code=413, detail="too many log entries in one batch")

    max_len = settings.frontend_log_max_message_length
    granted = _try_acquire_rate_slots(
        len(batch.entries), settings.frontend_log_rate_limit_per_minute
    )
    for entry in batch.entries[:granted]:
        parts = [_truncate(entry.message, max_len) or ""]
        if entry.url:
            parts.append(f"url={_truncate(entry.url, 500)}")
        if entry.ts:
            parts.append(f"client_ts={_truncate(entry.ts, 40)}")
        if entry.context:
            parts.append(f"context={_truncate(str(entry.context), max_len)}")
        if entry.stack:
            parts.append(f"stack:\n{_truncate(entry.stack, max_len)}")
        frontend_logger.log(_LEVEL_MAP[entry.level], "%s", " | ".join(parts))
    return FrontendLogIngestResult(accepted=granted, dropped=len(batch.entries) - granted)
