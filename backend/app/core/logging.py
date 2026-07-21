from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# root logger 上由本模块添加的 handler 都打上这个标记，方便重复调用（例如
# uvicorn --reload 触发的重新导入）时先精确摘掉旧 handler 再重建，不叠加。
_MANAGED_HANDLER_ATTR = "_news_caught_managed"

DEFAULT_LOG_DIRNAME = "logs"
DEFAULT_LOG_FILENAME = "backend.log"


def _default_log_file_path() -> Path:
    # backend/app/core/logging.py -> parents[2] == backend/
    return Path(__file__).resolve().parents[2] / "data" / DEFAULT_LOG_DIRNAME / DEFAULT_LOG_FILENAME


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def _build_formatter(log_format: str) -> logging.Formatter:
    if log_format == "json":
        return _JsonFormatter()
    return logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")


def configure_logging(
    level: str,
    *,
    file_enabled: bool = True,
    file_path: str | None = None,
    file_max_bytes: int = 10 * 1024 * 1024,
    file_backup_count: int = 5,
    log_format: str = "plain",
) -> None:
    """配置 root logger：控制台 handler + 可选的按大小轮转文件 handler。

    幂等：重复调用会先摘掉上一次由本函数添加的 handler 再重建，不会随重复
    调用无限叠加（uvicorn --reload 场景下同一进程可能多次调用）。
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in list(root_logger.handlers):
        if getattr(handler, _MANAGED_HANDLER_ATTR, False):
            root_logger.removeHandler(handler)
            handler.close()

    formatter = _build_formatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    setattr(console_handler, _MANAGED_HANDLER_ATTR, True)
    root_logger.addHandler(console_handler)

    if file_enabled:
        target_path = Path(file_path) if file_path else _default_log_file_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target_path,
            maxBytes=file_max_bytes,
            backupCount=file_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, _MANAGED_HANDLER_ATTR, True)
        root_logger.addHandler(file_handler)
