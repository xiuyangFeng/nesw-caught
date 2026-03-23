from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.main import app
from app.services.market_quote_producer import MarketQuoteProducer
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.workers import market_quote_producer as market_quote_worker


def test_market_quote_producer_run_cycle_publishes_refresh_event() -> None:
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.return_value = [
        {"symbol": "0700.HK", "price": 332.4, "status": "ok"},
        {"symbol": "AAPL", "price": 211.2, "status": "ok"},
    ]
    event_bus = MagicMock()

    producer = MarketQuoteProducer(
        session_factory=session_factory,
        quote_service_factory=lambda: quote_service,
        event_bus=event_bus,
        poll_interval_seconds=5.0,
    )

    producer.run_cycle()

    quote_service.refresh_watchlist_quotes.assert_called_once_with(session)
    event_bus.publish.assert_called_once_with(
        "market.watchlist_refreshed",
        {
            "symbols": ["0700.HK", "AAPL"],
            "quotes": [
                {"symbol": "0700.HK", "price": 332.4, "status": "ok"},
                {"symbol": "AAPL", "price": 211.2, "status": "ok"},
            ],
        },
    )


def test_market_quote_producer_run_cycle_persists_ok_runtime_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.return_value = [
        {"symbol": "0700.HK", "price": 332.4, "status": "ok"},
        {"symbol": "AAPL", "price": 211.2, "status": "ok"},
    ]
    event_bus = MagicMock()

    producer = MarketQuoteProducer(
        session_factory=TestingSessionLocal,
        quote_service_factory=lambda: quote_service,
        event_bus=event_bus,
        poll_interval_seconds=5.0,
    )

    producer.run_cycle()

    with TestingSessionLocal() as session:
        status = session.scalar(
            select(WorkerRuntimeStatus).where(WorkerRuntimeStatus.worker_name == "market_quote_producer")
        )

    assert status is not None
    assert status.status == "ok"
    assert status.cycle_count == 1
    assert status.success_count == 1
    assert status.failure_count == 0
    assert status.last_quotes_count == 2
    assert status.last_success_at is not None
    assert status.last_heartbeat_at is not None
    assert status.last_error is None


def test_market_quote_producer_run_cycle_skips_empty_watchlist() -> None:
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.return_value = []
    event_bus = MagicMock()

    producer = MarketQuoteProducer(
        session_factory=session_factory,
        quote_service_factory=lambda: quote_service,
        event_bus=event_bus,
        poll_interval_seconds=5.0,
    )

    producer.run_cycle()

    quote_service.refresh_watchlist_quotes.assert_called_once_with(session)
    event_bus.publish.assert_not_called()


def test_market_quote_producer_run_cycle_logs_and_survives_refresh_errors() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.side_effect = RuntimeError("provider timeout")
    event_bus = MagicMock()
    logger = MagicMock()

    producer = MarketQuoteProducer(
        session_factory=TestingSessionLocal,
        quote_service_factory=lambda: quote_service,
        event_bus=event_bus,
        poll_interval_seconds=5.0,
        logger=logger,
    )

    producer.run_cycle()

    event_bus.publish.assert_not_called()
    logger.exception.assert_called_once()
    with TestingSessionLocal() as session:
        status = session.scalar(
            select(WorkerRuntimeStatus).where(WorkerRuntimeStatus.worker_name == "market_quote_producer")
        )

    assert status is not None
    assert status.status == "degraded"
    assert status.cycle_count == 1
    assert status.success_count == 0
    assert status.failure_count == 1
    assert status.last_error == "provider timeout"
    assert status.last_failure_at is not None


def test_market_quote_producer_background_loop_can_start_and_stop() -> None:
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.return_value = []
    event_bus = MagicMock()

    producer = MarketQuoteProducer(
        session_factory=session_factory,
        quote_service_factory=lambda: quote_service,
        event_bus=event_bus,
        poll_interval_seconds=0.01,
    )

    producer.start()
    producer.stop(timeout=1.0)

    assert session_factory.called
    assert producer._thread is not None
    assert not producer._thread.is_alive()


def test_app_lifespan_does_not_start_market_quote_producer(monkeypatch) -> None:
    lifecycle: list[str] = []

    class FakeProducer:
        def start(self) -> None:
            lifecycle.append("start")

        def stop(self, timeout: float | None = None) -> None:
            lifecycle.append(f"stop:{timeout}")

    class FakeNotificationService:
        def start(self) -> None:
            lifecycle.append("notify-start")

        def stop(self) -> None:
            lifecycle.append("notify-stop")

    settings = Settings(market_quote_producer_enabled=True)
    monkeypatch.setattr("app.main.initialize_database", lambda: None)
    monkeypatch.setattr("app.main._register_event_handlers", lambda: None)
    monkeypatch.setattr("app.main.get_notification_service", lambda: FakeNotificationService())
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.build_market_quote_producer", lambda: FakeProducer())

    with TestClient(app):
        assert lifecycle == ["notify-start"]

    assert lifecycle == ["notify-start", "notify-stop"]


def test_market_quote_worker_main_initializes_runtime_and_starts_producer(monkeypatch) -> None:
    calls: list[str] = []

    class FakeProducer:
        def run_forever(self) -> None:
            calls.append("run-forever")

    class FakeEventBus:
        pass

    monkeypatch.setattr(market_quote_worker, "initialize_database", lambda: calls.append("init-db"))
    monkeypatch.setattr(market_quote_worker, "build_event_bus", lambda: calls.append("build-bus") or FakeEventBus())
    monkeypatch.setattr(
        market_quote_worker,
        "register_market_watchlist_handlers",
        lambda event_bus: calls.append(f"register-market:{event_bus.__class__.__name__}"),
    )
    monkeypatch.setattr(
        market_quote_worker,
        "build_market_quote_producer",
        lambda event_bus=None: calls.append(f"build-producer:{event_bus.__class__.__name__}") or FakeProducer(),
    )

    market_quote_worker.main()

    assert calls == [
        "init-db",
        "build-bus",
        "register-market:FakeEventBus",
        "build-producer:FakeEventBus",
        "run-forever",
    ]
