"""``configure_logging`` 的文件轮转/JSON 格式/幂等性测试（架构加固计划 Wave 3b Task 12）。

背景：升级前的 ``core/logging.py`` 只有 8 行 ``basicConfig``——只有控制台输出，
没有文件、没有轮转。多后台线程共写 SQLite 的系统一旦出现 ``database is
locked`` 之类问题，日志早已滚出终端缓冲区，事后基本无法定位。这里验证升级
后的实现：文件真正生成、轮转参数真正传给 ``RotatingFileHandler``、
``json`` 格式输出的字段齐全、重复调用（对应 uvicorn ``--reload``）不会让
handler 无限叠加导致日志重复打印。
"""
from __future__ import annotations

import json
import logging
import logging.handlers

import pytest

from app.core.logging import configure_logging

_MANAGED_HANDLER_ATTR = "_news_caught_managed"


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    """快照/还原 root logger，避免本文件的 handler 变更污染其余测试文件。"""
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    yield
    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.setLevel(original_level)


def _managed_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, _MANAGED_HANDLER_ATTR, False)]


def test_file_handler_creates_log_file_and_parent_dir(tmp_path):
    log_path = tmp_path / "nested" / "backend.log"
    assert not log_path.parent.exists()

    configure_logging(
        "INFO",
        file_enabled=True,
        file_path=str(log_path),
        file_max_bytes=1024,
        file_backup_count=2,
    )
    logging.getLogger("test.logging").info("hello")
    for handler in _managed_handlers():
        handler.flush()

    assert log_path.exists()
    assert "hello" in log_path.read_text(encoding="utf-8")


def test_file_disabled_skips_file_handler(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging("INFO", file_enabled=False, file_path=str(log_path))

    handlers = _managed_handlers()
    assert not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)
    assert not log_path.exists()


def test_rotation_config_is_applied(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging(
        "INFO",
        file_enabled=True,
        file_path=str(log_path),
        file_max_bytes=2048,
        file_backup_count=3,
    )

    file_handlers = [
        h for h in _managed_handlers() if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    assert file_handlers[0].maxBytes == 2048
    assert file_handlers[0].backupCount == 3


def test_json_format_includes_expected_fields(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging(
        "INFO",
        file_enabled=True,
        file_path=str(log_path),
        log_format="json",
    )
    logging.getLogger("test.logging.json").warning("something happened")
    for handler in _managed_handlers():
        handler.flush()

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "test.logging.json"
    assert payload["message"] == "something happened"
    assert "ts" in payload


def test_plain_format_is_not_json(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging(
        "INFO",
        file_enabled=True,
        file_path=str(log_path),
        log_format="plain",
    )
    logging.getLogger("test.logging.plain").info("plain message")
    for handler in _managed_handlers():
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "plain message" in content
    with pytest.raises(json.JSONDecodeError):
        json.loads(content.splitlines()[-1])


def test_repeated_calls_do_not_stack_handlers(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging("INFO", file_enabled=True, file_path=str(log_path))
    first_count = len(_managed_handlers())

    configure_logging("INFO", file_enabled=True, file_path=str(log_path))
    second_count = len(_managed_handlers())

    configure_logging("DEBUG", file_enabled=True, file_path=str(log_path))
    third_count = len(_managed_handlers())

    assert first_count == second_count == third_count
    assert logging.getLogger().level == logging.DEBUG


def test_repeated_calls_do_not_duplicate_log_lines(tmp_path):
    log_path = tmp_path / "backend.log"

    configure_logging("INFO", file_enabled=True, file_path=str(log_path))
    configure_logging("INFO", file_enabled=True, file_path=str(log_path))
    logging.getLogger("test.logging.dup").info("only once")
    for handler in _managed_handlers():
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert content.count("only once") == 1
