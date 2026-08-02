"""MarketOverviewProducer worker 与 main.py 接线测试（计划任务 B7）。

覆盖：
- do_cycle：调 MarketOverviewService.refresh_index_quotes 落库 + 触发板块缓存刷新；
  板块刷新失败仅记日志、不影响周期结果；不发 event_bus 事件
- get_interval：盘中 market_overview_poll_interval_seconds / 全市场闭市降频
  idle（用 any_overview_market_open 判定）
- 异常周期不崩溃（BaseWorker 记账）
- main.py lifespan：开关启停接线
- workers/market_overview_producer.py 独立进程入口
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.main import app
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.services.market_overview_producer import MarketOverviewProducer
from app.workers import market_overview_producer as market_overview_worker


def _make_record(symbol: str, status: str = "ok") -> MagicMock:
    record = MagicMock()
    record.symbol = symbol
    record.status = status
    return record


def _build_producer(
    session_factory,
    service: MagicMock,
    board_refresher: MagicMock | None = None,
    **kwargs,
) -> MarketOverviewProducer:
    return MarketOverviewProducer(
        session_factory=session_factory,
        overview_service_factory=lambda: service,
        board_refresher=board_refresher,
        poll_interval_seconds=60.0,
        idle_poll_interval_seconds=300.0,
        **kwargs,
    )


def test_do_cycle_refreshes_quotes_and_boards_without_event_bus() -> None:
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    service = MagicMock()
    service.refresh_index_quotes.return_value = [
        _make_record("^GSPC"),
        _make_record("^N225", status="fetch_failed"),
    ]
    board_refresher = MagicMock()

    producer = _build_producer(session_factory, service, board_refresher)

    processed = producer.do_cycle()

    service.refresh_index_quotes.assert_called_once_with(session)
    board_refresher.assert_called_once_with()
    # 返回成功落库的报价数（fetch_failed 不计）。
    assert processed == 1
    # producer 没有 event_bus 依赖（设计：不发布事件，前端走定时轮询）。
    assert not hasattr(producer, "event_bus")


def test_do_cycle_board_refresh_failure_does_not_fail_cycle() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    service = MagicMock()
    service.refresh_index_quotes.return_value = [_make_record("^GSPC")]
    board_refresher = MagicMock(side_effect=RuntimeError("eastmoney timeout"))
    logger = MagicMock()

    producer = _build_producer(testing_session, service, board_refresher, logger=logger)

    processed = producer.run_cycle()

    # 板块失败仅记日志：周期仍按成功记账。
    assert processed == 1
    assert logger.warning.called
    with testing_session() as session:
        status = session.scalar(
            select(WorkerRuntimeStatus).where(
                WorkerRuntimeStatus.worker_name == "market_overview_producer"
            )
        )
    assert status is not None
    assert status.status == "ok"
    assert status.failure_count == 0


def test_do_cycle_service_error_recorded_and_cycle_survives() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    service = MagicMock()
    service.refresh_index_quotes.side_effect = RuntimeError("yahoo down")
    board_refresher = MagicMock()
    logger = MagicMock()

    producer = _build_producer(testing_session, service, board_refresher, logger=logger)

    processed = producer.run_cycle()

    assert processed == 0
    # 指数刷新失败时整周期失败，板块刷新不执行（下一轮再试）。
    board_refresher.assert_not_called()
    logger.exception.assert_called_once()
    with testing_session() as session:
        status = session.scalar(
            select(WorkerRuntimeStatus).where(
                WorkerRuntimeStatus.worker_name == "market_overview_producer"
            )
        )
    assert status is not None
    assert status.status == "degraded"
    assert status.failure_count == 1


def test_get_interval_poll_when_any_overview_market_open(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.market_overview_producer.any_overview_market_open", lambda: True
    )
    producer = _build_producer(MagicMock(), MagicMock())

    assert producer.get_interval() == 60.0


def test_get_interval_idle_when_all_overview_markets_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.market_overview_producer.any_overview_market_open", lambda: False
    )
    producer = _build_producer(MagicMock(), MagicMock())

    assert producer.get_interval() == 300.0


def test_app_lifespan_starts_market_overview_producer_when_enabled(monkeypatch) -> None:
    lifecycle: list[str] = []

    class FakeProducer:
        def start(self) -> None:
            lifecycle.append("overview-start")

        def stop(self, timeout: float | None = None) -> None:
            lifecycle.append("overview-stop")

    class FakeNotificationService:
        def start(self) -> None:
            lifecycle.append("notify-start")

        def stop(self) -> None:
            lifecycle.append("notify-stop")

    settings = Settings(
        market_quote_producer_enabled=False,
        market_overview_producer_enabled=True,
    )
    monkeypatch.setattr("app.main.initialize_database", lambda: None)
    monkeypatch.setattr("app.main._register_event_handlers", lambda: None)
    monkeypatch.setattr("app.main.get_notification_service", lambda: FakeNotificationService())
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.main.build_market_overview_producer",
        lambda: lifecycle.append("overview-build") or FakeProducer(),
    )

    with TestClient(app):
        assert lifecycle == ["notify-start", "overview-build", "overview-start"]

    assert lifecycle == ["notify-start", "overview-build", "overview-start", "overview-stop", "notify-stop"]


def test_app_lifespan_skips_market_overview_producer_when_disabled(monkeypatch) -> None:
    lifecycle: list[str] = []
    build_calls: list[object] = []

    class FakeNotificationService:
        def start(self) -> None:
            lifecycle.append("notify-start")

        def stop(self) -> None:
            lifecycle.append("notify-stop")

    settings = Settings(
        market_quote_producer_enabled=False,
        market_overview_producer_enabled=False,
    )
    monkeypatch.setattr("app.main.initialize_database", lambda: None)
    monkeypatch.setattr("app.main._register_event_handlers", lambda: None)
    monkeypatch.setattr("app.main.get_notification_service", lambda: FakeNotificationService())
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.main.build_market_overview_producer",
        lambda: build_calls.append(object()) or MagicMock(),
    )

    with TestClient(app):
        assert lifecycle == ["notify-start"]

    assert lifecycle == ["notify-start", "notify-stop"]
    assert build_calls == []


def test_market_overview_worker_main_initializes_and_runs_forever(monkeypatch) -> None:
    calls: list[str] = []

    class FakeProducer:
        def run_forever(self) -> None:
            calls.append("run-forever")

    monkeypatch.setattr(
        market_overview_worker, "initialize_database", lambda: calls.append("init-db")
    )
    monkeypatch.setattr(
        market_overview_worker,
        "build_market_overview_producer",
        lambda: calls.append("build-producer") or FakeProducer(),
    )

    market_overview_worker.main()

    assert calls == ["init-db", "build-producer", "run-forever"]
