"""后台 X 健康探针 worker 的回归测试。

配套的行为改动见 `api/routes/health.py`：`/health` 不再在请求线程里发起最长 60 秒
的 twitterapi.io 探针，改为读 `x_source_health` 的上次探测结果。本 worker 负责让
那份结果保持新鲜，否则 /health 会长期把健康的 X 监控报成 unknown。
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.x_source_health import XSourceHealth
from app.services.x_monitor.constants import PROVIDER_NAME
from app.workers import x_health_probe_worker as worker_module
from app.workers.x_health_probe_worker import XHealthProbeWorker


def _enabled_settings() -> Settings:
    return Settings(x_monitor_enabled=True, twitterapi_io_api_key="test-key")


def _reset_health() -> None:
    with SessionLocal() as session:
        session.query(XSourceHealth).filter(XSourceHealth.provider_name == PROVIDER_NAME).delete()
        session.commit()


def _load_health() -> XSourceHealth | None:
    with SessionLocal() as session:
        return session.query(XSourceHealth).filter(
            XSourceHealth.provider_name == PROVIDER_NAME
        ).one_or_none()


@pytest.fixture(autouse=True)
def _isolate_x_source_health():
    """前后都清干净 `x_source_health`。

    测试库是整个 session 共用的一个 SQLite 文件，这张表只有一行（provider 唯一）。
    留下残留行会让后面按字母序执行的 test_x_monitor.py 里的 /health 断言读到
    本文件写入的探测结果 —— 首次实现时就是这么把它跑挂的。
    """
    _reset_health()
    yield
    _reset_health()


def test_probe_records_success(monkeypatch) -> None:
    _reset_health()
    monkeypatch.setattr(worker_module, "get_settings", _enabled_settings)
    monkeypatch.setattr(
        worker_module.XMonitorService, "provider_health", lambda self: (True, "configured")
    )

    processed = XHealthProbeWorker(session_factory=SessionLocal).do_cycle()

    assert processed == 1
    health = _load_health()
    assert health is not None
    assert health.last_success_at is not None
    assert health.consecutive_failures == 0
    assert health.last_error is None


def test_probe_records_failure_and_streak(monkeypatch) -> None:
    _reset_health()
    monkeypatch.setattr(worker_module, "get_settings", _enabled_settings)
    monkeypatch.setattr(
        worker_module.XMonitorService, "provider_health", lambda self: (False, "rate limited")
    )

    probe = XHealthProbeWorker(session_factory=SessionLocal)
    probe.do_cycle()
    probe.do_cycle()

    health = _load_health()
    assert health is not None
    assert health.consecutive_failures == 2
    assert health.last_error == "rate limited"
    assert health.last_success_at is None


def test_probe_records_exception_as_failure_with_type_name(monkeypatch) -> None:
    """探针自身抛异常也要落库，且错误信息必须带异常类型名。

    httpx 的超时类异常 str(exc) 往往是空串——线上 source_health.last_error 全空
    正是这么来的，这里不能重蹈覆辙。
    """
    _reset_health()
    monkeypatch.setattr(worker_module, "get_settings", _enabled_settings)

    def _boom(self):
        raise TimeoutError("")

    monkeypatch.setattr(worker_module.XMonitorService, "provider_health", _boom)

    XHealthProbeWorker(session_factory=SessionLocal).do_cycle()

    health = _load_health()
    assert health is not None
    assert health.consecutive_failures == 1
    assert "TimeoutError" in (health.last_error or "")


def test_probe_is_noop_when_disabled(monkeypatch) -> None:
    _reset_health()
    monkeypatch.setattr(worker_module, "get_settings", lambda: Settings(x_monitor_enabled=False))

    def _must_not_probe(self):  # pragma: no cover - 断言它不被调用
        raise AssertionError("provider_health must not be called when x monitor is disabled")

    monkeypatch.setattr(worker_module.XMonitorService, "provider_health", _must_not_probe)

    assert XHealthProbeWorker(session_factory=SessionLocal).do_cycle() == 0
    assert _load_health() is None


def test_probe_does_not_hold_write_transaction_across_network(monkeypatch) -> None:
    """网络探针必须发生在写事务之外：写锁不得跨越最长 60 秒的外网往返。"""
    _reset_health()
    monkeypatch.setattr(worker_module, "get_settings", _enabled_settings)

    events: list[str] = []
    real_factory = SessionLocal

    def tracking_factory():
        events.append("session_open")
        return real_factory()

    def _probe(self):
        events.append("network")
        return True, "configured"

    monkeypatch.setattr(worker_module.XMonitorService, "provider_health", _probe)

    XHealthProbeWorker(session_factory=tracking_factory).do_cycle()

    # 写库用的那次 session 必须在网络调用之后才打开。
    assert events.index("network") < len(events) - 1
    assert events[-1] == "session_open"
