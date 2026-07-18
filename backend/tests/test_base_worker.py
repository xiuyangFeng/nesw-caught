"""BaseWorker 记账兜底(_record_success / _record_failure)异常处理行为测试。

治理背景:审查异常收窄时,曾尝试把这两个方法的 `except Exception` 收窄为
`sqlalchemy.exc.SQLAlchemyError`。但 backend/tests/test_news_ingest_scheduler.py::
test_scheduler_drains_signal_backlog 用一个不完整模拟真实 Session 接口的
`FakeSession`(没有 `.scalar()` 方法)作为 session_factory,导致记账时抛出的是
`AttributeError` 而非 `SQLAlchemyError`。收窄后该 AttributeError 不再被
_record_failure 吞掉,而是穿透 run_cycle() 向上抛出,破坏了
"run_cycle() 从不崩溃、失败只降级为返回 0" 的对外契约,是一次真实的行为回归。

因此这两个方法的 `except Exception` 予以保留(不收窄),仅确认:
  - 记账阶段无论抛出什么类型异常都会被吞掉并记录带 worker 名称的 exception 日志;
  - run_cycle() 的返回值契约不受记账失败影响。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from app.workers.base_worker import BaseWorker


class _StubWorker(BaseWorker):
    worker_name = "stub_worker_for_tests"

    def do_cycle(self) -> int:
        return 0


def _session_factory_raising(exc: Exception):
    @contextmanager
    def factory():
        session = MagicMock()
        session.scalar.side_effect = exc
        yield session

    return factory


class _BareSession:
    """故意不实现 .scalar() 的最小 session 替身,模拟测试替身/未来实现与真实
    SQLAlchemy Session 接口不完全一致的场景(参见 test_scheduler_drains_signal_backlog)。
    """

    def commit(self) -> None:
        return None

    def __enter__(self) -> _BareSession:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def test_record_success_swallows_sqlalchemy_error_and_logs_with_worker_name(caplog) -> None:
    logger = logging.getLogger("test.base_worker.success")
    worker = _StubWorker(
        session_factory=_session_factory_raising(SQLAlchemyError("db down")),
        logger=logger,
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        worker._record_success(3)  # 不应抛出

    assert any(
        "stub_worker_for_tests" in record.message and record.levelno >= logging.ERROR
        for record in caplog.records
    )


def test_record_failure_swallows_sqlalchemy_error_and_logs_with_worker_name(caplog) -> None:
    logger = logging.getLogger("test.base_worker.failure")
    worker = _StubWorker(
        session_factory=_session_factory_raising(SQLAlchemyError("db down")),
        logger=logger,
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        worker._record_failure("boom")  # 不应抛出

    assert any(
        "stub_worker_for_tests" in record.message and record.levelno >= logging.ERROR
        for record in caplog.records
    )


def test_record_success_swallows_non_sqlalchemy_session_errors_and_logs(caplog) -> None:
    """回归测试:session_factory 产出不完整模拟真实 Session 接口的替身
    (缺少 .scalar())时抛出的 AttributeError,也必须被吞掉而不是让调用方崩溃。
    """
    logger = logging.getLogger("test.base_worker.success.bare_session")
    worker = _StubWorker(session_factory=lambda: _BareSession(), logger=logger)

    with caplog.at_level(logging.ERROR, logger=logger.name):
        worker._record_success(1)  # 不应抛出 AttributeError

    assert any(
        "stub_worker_for_tests" in record.message and record.levelno >= logging.ERROR
        for record in caplog.records
    )


def test_record_failure_swallows_non_sqlalchemy_session_errors_and_logs(caplog) -> None:
    logger = logging.getLogger("test.base_worker.failure.bare_session")
    worker = _StubWorker(session_factory=lambda: _BareSession(), logger=logger)

    with caplog.at_level(logging.ERROR, logger=logger.name):
        worker._record_failure("boom")  # 不应抛出 AttributeError

    assert any(
        "stub_worker_for_tests" in record.message and record.levelno >= logging.ERROR
        for record in caplog.records
    )


def test_run_cycle_still_returns_processed_count_when_record_success_hits_db_error() -> None:
    """外部可观察行为不变:即使记账失败(任意异常类型),run_cycle 的返回值仍是 do_cycle 的结果。"""

    class _CountingWorker(BaseWorker):
        worker_name = "counting_worker_for_tests"

        def do_cycle(self) -> int:
            return 7

    worker = _CountingWorker(session_factory=_session_factory_raising(SQLAlchemyError("db down")))

    assert worker.run_cycle() == 7


def test_run_cycle_never_raises_when_record_failure_hits_non_sqlalchemy_session_error() -> None:
    """外部可观察行为不变:do_cycle 失败 + 记账阶段又遇到非 SQLAlchemy 异常(替身 session)时,
    run_cycle() 仍必须优雅返回 0,而不是让异常穿透(此前的收窄尝试曾破坏这一契约)。
    """

    class _FailingWorker(BaseWorker):
        worker_name = "failing_worker_for_tests"

        def do_cycle(self) -> int:
            raise RuntimeError("do_cycle boom")

    worker = _FailingWorker(session_factory=lambda: _BareSession())

    assert worker.run_cycle() == 0


class _RecordingSession:
    """记录 commit 次数的最小 session 替身,供心跳节流断言写库次数。"""

    def __init__(self) -> None:
        self.commit_count = 0

    def __enter__(self) -> _RecordingSession:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def scalar(self, *args, **kwargs):
        return None

    def add(self, instance) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1


def test_record_success_throttles_idle_heartbeats_within_interval() -> None:
    """空闲周期(processed_count==0)距上次心跳 <30s 时跳过写库;有处理量时不节流。"""
    session = _RecordingSession()
    worker = _StubWorker(session_factory=lambda: session)

    worker._record_success(0)  # 首次心跳:写
    worker._record_success(0)  # 30s 内空闲:跳过
    worker._record_success(0)
    assert session.commit_count == 1

    worker._record_success(3)  # 有处理量:不受空闲节流限制
    assert session.commit_count == 2


def test_record_success_writes_idle_heartbeat_again_after_interval(monkeypatch) -> None:
    """空闲超过节流间隔后,下一次心跳恢复写库。"""
    session = _RecordingSession()
    worker = _StubWorker(session_factory=lambda: session)
    now = [1000.0]
    monkeypatch.setattr("app.workers.base_worker.time.monotonic", lambda: now[0])

    worker._record_success(0)
    worker._record_success(0)
    assert session.commit_count == 1

    now[0] += 31.0
    worker._record_success(0)
    assert session.commit_count == 2


def test_queue_worker_idle_throttle_uses_base_worker_implementation() -> None:
    """queue_worker 的重复节流实现已下沉:子类不再自带 _last_heartbeat_at 覆盖逻辑。"""
    from app.workers.queue_worker import BackgroundQueueWorker

    session = _RecordingSession()
    worker = BackgroundQueueWorker(session_factory=lambda: session)
    assert "_record_success" not in BackgroundQueueWorker.__dict__

    worker._record_success(0)
    worker._record_success(0)
    assert session.commit_count == 1
