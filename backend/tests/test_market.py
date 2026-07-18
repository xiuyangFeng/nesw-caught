from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from app.api.routes import market as market_routes
from app.db.session import SessionLocal
from app.main import app
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.market_chart_service import MarketChartService
from app.services.quote_provider import normalize_symbol
from app.services.quote_service import QuoteService


def test_market_watchlist_quotes_return_expanded_fields(monkeypatch) -> None:
    class FakeQuoteService:
        def get_cached_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
            return [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "display_name": "Tencent",
                    "provider_symbol": "0700.HK",
                    "price": 332.4,
                    "change_amount": 10.7,
                    "change_percent": 3.33,
                    "open_price": 325.0,
                    "previous_close": 321.7,
                    "day_high": 334.8,
                    "day_low": 323.2,
                    "volume": 18233000,
                    "status": "ok",
                    "source": "yahoo_finance",
                    "message": None,
                    "fetched_at": "2026-03-16T12:00:00Z",
                }
            ]

    monkeypatch.setattr(market_routes, "get_quote_service", lambda: FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["symbol"] == "0700.HK"
    assert payload[0]["open_price"] == 325.0
    assert payload[0]["previous_close"] == 321.7
    assert payload[0]["day_high"] == 334.8
    assert payload[0]["day_low"] == 323.2
    assert payload[0]["status"] == "ok"
    assert payload[0]["source"] == "yahoo_finance"


def test_quote_service_keeps_display_name_for_a_share_alias_lookup() -> None:
    service = QuoteService()

    with SessionLocal() as session:
        existing_item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "600519.SH").one_or_none()
        if existing_item is not None:
            session.delete(existing_item)
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()

        session.add(
            WatchlistItem(
                symbol="600519.SH",
                market="cn",
                display_name="贵州茅台",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.add(
            PriceSnapshot(
                symbol="600519.SH",
                market="cn",
                price=1688.8,
                change_amount=12.5,
                change_percent=0.75,
                open_price=1670.0,
                previous_close=1676.3,
                day_high=1699.0,
                day_low=1668.0,
                volume=928000,
                provider_name="yahoo_finance",
                provider_symbol="600519.SS",
                quote_status="ok",
                status_message=None,
                fetched_at=datetime.now(UTC),
            )
        )
        session.commit()

        payload = service.get_cached_symbol_quote("SH600519", session)

        assert payload["symbol"] == "600519.SH"
        assert payload["display_name"] == "贵州茅台"
        assert payload["provider_symbol"] == "600519.SS"

        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "600519.SH").one_or_none()
        if item is not None:
            session.delete(item)
        session.commit()


def test_quote_service_reads_cached_watchlist_quote_for_legacy_a_share_alias_row() -> None:
    service = QuoteService()

    with SessionLocal() as session:
        existing_item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if existing_item is not None:
            session.delete(existing_item)
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()

        session.add(
            WatchlistItem(
                symbol="SH600519",
                market="cn",
                display_name="贵州茅台",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.add(
            PriceSnapshot(
                symbol="600519.SH",
                market="cn",
                price=1688.8,
                change_amount=12.5,
                change_percent=0.75,
                open_price=1670.0,
                previous_close=1676.3,
                day_high=1699.0,
                day_low=1668.0,
                volume=928000,
                provider_name="yahoo_finance",
                provider_symbol="600519.SS",
                quote_status="ok",
                status_message=None,
                fetched_at=datetime.now(UTC),
            )
        )
        session.commit()

        payload = service.get_cached_watchlist_quotes(session)

        row = next(item for item in payload if item["display_name"] == "贵州茅台")
        assert row["symbol"] == "600519.SH"
        assert row["display_name"] == "贵州茅台"
        assert row["status"] == "ok"

        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if item is not None:
            session.delete(item)
        session.commit()


def test_quote_service_refresh_uses_canonical_cached_snapshot_for_legacy_a_share_alias_row() -> None:
    service = QuoteService()

    with SessionLocal() as session:
        existing_item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if existing_item is not None:
            session.delete(existing_item)
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()

        session.add(
            WatchlistItem(
                symbol="SH600519",
                market="cn",
                display_name="贵州茅台",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.add(
            PriceSnapshot(
                symbol="600519.SH",
                market="cn",
                price=1688.8,
                change_amount=12.5,
                change_percent=0.75,
                open_price=1670.0,
                previous_close=1676.3,
                day_high=1699.0,
                day_low=1668.0,
                volume=928000,
                provider_name="yahoo_finance",
                provider_symbol="600519.SS",
                quote_status="ok",
                status_message=None,
                fetched_at=datetime.now(UTC),
            )
        )
        session.commit()

        with patch.object(service.provider, "fetch_quote", side_effect=RuntimeError("provider down")) as fetch_quote:
            payload = service.refresh_watchlist_quotes(session)

        row = next(item for item in payload if item["display_name"] == "贵州茅台")
        assert row["symbol"] == "600519.SH"
        assert row["status"] == "ok"
        assert all(call.args[0].provider_symbol != "600519.SS" for call in fetch_quote.call_args_list)

        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if item is not None:
            session.delete(item)
        session.commit()


def test_quote_service_resolves_canonical_a_share_input_against_legacy_watchlist_row() -> None:
    service = QuoteService()

    with SessionLocal() as session:
        existing_item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if existing_item is not None:
            session.delete(existing_item)
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()

        session.add(
            WatchlistItem(
                symbol="SH600519",
                market="cn",
                display_name="贵州茅台",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.add(
            PriceSnapshot(
                symbol="600519.SH",
                market="cn",
                price=1688.8,
                change_amount=12.5,
                change_percent=0.75,
                open_price=1670.0,
                previous_close=1676.3,
                day_high=1699.0,
                day_low=1668.0,
                volume=928000,
                provider_name="yahoo_finance",
                provider_symbol="600519.SS",
                quote_status="ok",
                status_message=None,
                fetched_at=datetime.now(UTC),
            )
        )
        session.commit()

        payload = service.get_cached_symbol_quote("600519.SH", session)

        assert payload["symbol"] == "600519.SH"
        assert payload["display_name"] == "贵州茅台"
        assert payload["provider_symbol"] == "600519.SS"

        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if item is not None:
            session.delete(item)
        session.commit()


def test_market_chart_service_resolves_canonical_a_share_input_against_legacy_watchlist_row() -> None:
    service = MarketChartService()

    with SessionLocal() as session:
        existing_item = session.query(WatchlistItem).filter(WatchlistItem.symbol == "SH600519").one_or_none()
        if existing_item is not None:
            session.delete(existing_item)
        session.commit()

        session.add(
            WatchlistItem(
                symbol="SH600519",
                market="cn",
                display_name="贵州茅台",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.commit()

        item = service._require_watchlist_symbol("600519.SH", session)

        assert item.symbol == "SH600519"
        assert item.display_name == "贵州茅台"

        session.delete(item)
        session.commit()


def test_market_symbol_detail_normalizes_hk_alias(monkeypatch) -> None:
    class FakeQuoteService:
        def __init__(self) -> None:
            self.received_symbol: str | None = None

        def get_cached_symbol_quote(self, symbol, session):  # pragma: no cover - exercised through route
            self.received_symbol = symbol
            return {
                "symbol": symbol,
                "market": "hk",
                "display_name": "智谱",
                "provider_symbol": "0253.HK",
                "price": 18.25,
                "change_amount": 0.5,
                "change_percent": 2.82,
                "open_price": 17.9,
                "previous_close": 17.75,
                "day_high": 18.4,
                "day_low": 17.6,
                "volume": 1200000,
                "status": "ok",
                "source": "yahoo_finance",
                "message": None,
                "is_abnormal": False,
                "abnormal_reason": None,
                "fetched_at": "2026-03-16T12:05:00Z",
            }

    fake_service = FakeQuoteService()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: fake_service, raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/HK253")

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.received_symbol == "HK253"
    assert payload["provider_symbol"] == "0253.HK"
    assert payload["symbol"] == "HK253"


def test_normalize_symbol_supports_a_share_aliases() -> None:
    canonical_sh = normalize_symbol("600519.SH")
    prefix_sh = normalize_symbol("SH600519")
    bare_sh = normalize_symbol("600519")
    inferred_sh = normalize_symbol("600519", "cn")
    canonical_sz = normalize_symbol("000001.SZ")
    prefix_sz = normalize_symbol("SZ000001")
    bare_sz = normalize_symbol("000001")
    inferred_sz = normalize_symbol("000001", "cn")

    assert canonical_sh.market == "cn"
    assert canonical_sh.provider_symbol == "600519.SS"
    assert prefix_sh.provider_symbol == "600519.SS"
    assert bare_sh.provider_symbol == "600519.SS"
    assert inferred_sh.provider_symbol == "600519.SS"
    assert canonical_sz.market == "cn"
    assert canonical_sz.provider_symbol == "000001.SZ"
    assert prefix_sz.provider_symbol == "000001.SZ"
    assert bare_sz.provider_symbol == "000001.SZ"
    assert inferred_sz.provider_symbol == "000001.SZ"


def test_market_symbol_detail_normalizes_a_share_alias(monkeypatch) -> None:
    class FakeQuoteService:
        def __init__(self) -> None:
            self.received_symbol: str | None = None

        def get_cached_symbol_quote(self, symbol, session):  # pragma: no cover - exercised through route
            self.received_symbol = symbol
            return {
                "symbol": symbol,
                "market": "cn",
                "display_name": "贵州茅台",
                "provider_symbol": "600519.SS",
                "price": 1688.8,
                "change_amount": 12.5,
                "change_percent": 0.75,
                "open_price": 1670.0,
                "previous_close": 1676.3,
                "day_high": 1699.0,
                "day_low": 1668.0,
                "volume": 928000,
                "status": "ok",
                "source": "yahoo_finance",
                "message": None,
                "is_abnormal": False,
                "abnormal_reason": None,
                "fetched_at": "2026-03-30T07:00:00Z",
            }

    fake_service = FakeQuoteService()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: fake_service, raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/SH600519")

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.received_symbol == "SH600519"
    assert payload["provider_symbol"] == "600519.SS"
    assert payload["symbol"] == "SH600519"


def test_market_watchlist_quotes_keep_partial_failures_visible(monkeypatch) -> None:
    class FakeQuoteService:
        def get_cached_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
            return [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "display_name": "Tencent",
                    "provider_symbol": "0700.HK",
                    "price": 332.4,
                    "change_amount": 10.7,
                    "change_percent": 3.33,
                    "open_price": 325.0,
                    "previous_close": 321.7,
                    "day_high": 334.8,
                    "day_low": 323.2,
                    "volume": 18233000,
                    "status": "ok",
                    "source": "yahoo_finance",
                    "message": None,
                    "fetched_at": "2026-03-16T12:00:00Z",
                },
                {
                    "symbol": "HK253",
                    "market": "hk",
                    "display_name": "智谱",
                    "provider_symbol": "0253.HK",
                    "price": None,
                    "change_amount": None,
                    "change_percent": None,
                    "open_price": None,
                    "previous_close": None,
                    "day_high": None,
                    "day_low": None,
                    "volume": None,
                    "status": "fetch_failed",
                    "source": "yahoo_finance",
                    "message": "upstream timeout",
                    "fetched_at": "2026-03-16T12:00:00Z",
                },
            ]

    monkeypatch.setattr(market_routes, "get_quote_service", lambda: FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    failed = next(item for item in payload if item["symbol"] == "HK253")
    assert failed["status"] == "fetch_failed"
    assert failed["message"] == "upstream timeout"


def test_market_watchlist_quotes_only_alert_on_threshold_entry(monkeypatch) -> None:
    from app.db.session import SessionLocal
    from app.models.notification_job import NotificationJob

    class FakeQuoteService:
        def __init__(self) -> None:
            self.responses = [
                [
                    {
                        "symbol": "0700.HK",
                        "market": "hk",
                        "display_name": "Tencent",
                        "provider_symbol": "0700.HK",
                        "price": 332.4,
                        "change_amount": 10.7,
                        "change_percent": 3.33,
                        "open_price": 325.0,
                        "previous_close": 321.7,
                        "day_high": 334.8,
                        "day_low": 323.2,
                        "volume": 18233000,
                        "status": "ok",
                        "source": "yahoo_finance",
                        "message": None,
                        "fetched_at": "2026-03-16T12:00:00Z",
                    }
                ],
                [
                    {
                        "symbol": "0700.HK",
                        "market": "hk",
                        "display_name": "Tencent",
                        "provider_symbol": "0700.HK",
                        "price": 333.1,
                        "change_amount": 11.4,
                        "change_percent": 3.55,
                        "open_price": 325.0,
                        "previous_close": 321.7,
                        "day_high": 334.8,
                        "day_low": 323.2,
                        "volume": 18233000,
                        "status": "ok",
                        "source": "yahoo_finance",
                        "message": None,
                        "fetched_at": "2026-03-16T12:01:00Z",
                    }
                ],
                [
                    {
                        "symbol": "0700.HK",
                        "market": "hk",
                        "display_name": "Tencent",
                        "provider_symbol": "0700.HK",
                        "price": 325.0,
                        "change_amount": 1.0,
                        "change_percent": 0.31,
                        "open_price": 325.0,
                        "previous_close": 321.7,
                        "day_high": 334.8,
                        "day_low": 323.2,
                        "volume": 18233000,
                        "status": "ok",
                        "source": "yahoo_finance",
                        "message": None,
                        "fetched_at": "2026-03-16T12:02:00Z",
                    }
                ],
                [
                    {
                        "symbol": "0700.HK",
                        "market": "hk",
                        "display_name": "Tencent",
                        "provider_symbol": "0700.HK",
                        "price": 334.2,
                        "change_amount": 12.5,
                        "change_percent": 3.88,
                        "open_price": 325.0,
                        "previous_close": 321.7,
                        "day_high": 334.8,
                        "day_low": 323.2,
                        "volume": 18233000,
                        "status": "ok",
                        "source": "yahoo_finance",
                        "message": None,
                        "fetched_at": "2026-03-16T12:03:00Z",
                    }
                ],
            ]

        def refresh_watchlist_quotes(self, session):  # pragma: no cover - exercised through producer
            return self.responses.pop(0)

    class FakeWatchlistRepository:
        def __init__(self, session) -> None:
            self.session = session

        def list_all(self):  # pragma: no cover - exercised through route
            item = MagicMock()
            item.symbol = "0700.HK"
            item.display_name = "Tencent"
            item.alert_threshold = 3.0
            return [item]

    from app.services.notification_service import NotificationService

    with SessionLocal() as session:
        session.query(NotificationJob).delete()
        session.commit()

    notification_service = NotificationService()
    config = MagicMock()
    config.alert_enabled = True
    fake_service = FakeQuoteService()
    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    from app import main as main_module

    fake_bus = FakeBus()
    monkeypatch.setattr(main_module, "build_event_bus", lambda: fake_bus)
    monkeypatch.setattr(main_module, "WatchlistRepository", FakeWatchlistRepository)
    monkeypatch.setattr(main_module, "get_notification_service", lambda: notification_service)
    monkeypatch.setattr(main_module, "get_quote_service", lambda: fake_service)
    main_module._register_event_handlers()
    main_module.register_market_watchlist_handlers(fake_bus)

    with patch.object(notification_service, "_load_config", return_value=config):
        producer = main_module.build_market_quote_producer()
        producer.run_cycle()
        producer.run_cycle()
        producer.run_cycle()
        producer.run_cycle()

    with SessionLocal() as session:
        jobs = session.query(NotificationJob).filter(NotificationJob.event_type == "watchlist_alert").all()
        assert len(jobs) == 2


def test_market_watchlist_quotes_read_cached_payload_without_publishing_refresh_event(monkeypatch) -> None:
    class FakeQuoteService:
        def get_cached_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
            return [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "display_name": "Tencent",
                    "provider_symbol": "0700.HK",
                    "price": 332.4,
                    "change_amount": 10.7,
                    "change_percent": 3.33,
                    "open_price": 325.0,
                    "previous_close": 321.7,
                    "day_high": 334.8,
                    "day_low": 323.2,
                    "volume": 18233000,
                    "status": "ok",
                    "source": "yahoo_finance",
                    "message": None,
                    "fetched_at": "2026-03-16T12:00:00Z",
                    "is_abnormal": True,
                    "abnormal_reason": "price_move",
                }
            ]

    class FakeBus:
        def __init__(self) -> None:
            self.published: list[tuple[str, dict[str, object]]] = []

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))

    class ExplodingNotificationService:
        def on_watchlist_alert(self, payload):  # pragma: no cover - should not be called
            raise AssertionError("route should not call notification service directly")

    fake_bus = FakeBus()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: FakeQuoteService(), raising=False)
    monkeypatch.setattr(market_routes, "get_event_bus", lambda: fake_bus, raising=False)
    monkeypatch.setattr(market_routes, "get_notification_service", lambda: ExplodingNotificationService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/watchlist")

    assert response.status_code == 200
    assert fake_bus.published == []


def test_market_symbol_detail_reads_cached_quote_payload(monkeypatch) -> None:
    class FakeQuoteService:
        def __init__(self) -> None:
            self.received_symbol: str | None = None

        def get_cached_symbol_quote(self, symbol, session):  # pragma: no cover - exercised through route
            self.received_symbol = symbol
            return {
                "symbol": symbol,
                "market": "us",
                "display_name": "Apple",
                "provider_symbol": "AAPL",
                "price": 211.2,
                "change_amount": 1.5,
                "change_percent": 0.72,
                "open_price": 210.0,
                "previous_close": 209.7,
                "day_high": 212.0,
                "day_low": 208.8,
                "volume": 1500000,
                "status": "ok",
                "source": "yahoo_finance",
                "message": None,
                "is_abnormal": False,
                "abnormal_reason": None,
                "fetched_at": "2026-03-16T12:05:00Z",
            }

    fake_service = FakeQuoteService()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: fake_service, raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/AAPL")

    assert response.status_code == 200
    assert fake_service.received_symbol == "AAPL"


def test_market_watchlist_quotes_return_unavailable_payload_from_cache_reader(monkeypatch) -> None:
    class FakeQuoteService:
        def get_cached_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
            return [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "display_name": "Tencent",
                    "provider_symbol": "0700.HK",
                    "price": None,
                    "change_amount": None,
                    "change_percent": None,
                    "open_price": None,
                    "previous_close": None,
                    "day_high": None,
                    "day_low": None,
                    "volume": None,
                    "status": "unavailable",
                    "source": "yahoo_finance",
                    "message": "quote not produced yet",
                    "fetched_at": "2026-03-16T12:00:00Z",
                    "is_abnormal": False,
                    "abnormal_reason": None,
                }
            ]

    monkeypatch.setattr(market_routes, "get_quote_service", lambda: FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/watchlist")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["status"] == "unavailable"
    assert payload[0]["message"] == "quote not produced yet"


def test_market_refresh_route_runs_one_shot_refresh_and_publishes_event(monkeypatch) -> None:
    class FakeQuoteService:
        def refresh_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
            return [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "display_name": "Tencent",
                    "provider_symbol": "0700.HK",
                    "price": 332.4,
                    "change_amount": 10.7,
                    "change_percent": 3.33,
                    "open_price": 325.0,
                    "previous_close": 321.7,
                    "day_high": 334.8,
                    "day_low": 323.2,
                    "volume": 18233000,
                    "status": "ok",
                    "source": "yahoo_finance",
                    "message": None,
                    "fetched_at": "2026-03-16T12:00:00Z",
                    "is_abnormal": True,
                    "abnormal_reason": "price_move",
                }
            ]

    class FakeBus:
        def __init__(self) -> None:
            self.published: list[tuple[str, dict[str, object]]] = []

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))

    fake_bus = FakeBus()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: FakeQuoteService(), raising=False)
    monkeypatch.setattr(market_routes, "get_event_bus", lambda: fake_bus, raising=False)
    client = TestClient(app)

    response = client.post("/api/market/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["quotes_count"] == 1
    assert payload["symbols"] == ["0700.HK"]
    assert payload["triggered_at"] is not None
    assert fake_bus.published == [
        (
            "market.watchlist_refreshed",
            {
                "symbols": ["0700.HK"],
                "quotes": [
                    {
                        "symbol": "0700.HK",
                        "market": "hk",
                        "display_name": "Tencent",
                        "provider_symbol": "0700.HK",
                        "price": 332.4,
                        "change_amount": 10.7,
                        "change_percent": 3.33,
                        "open_price": 325.0,
                        "previous_close": 321.7,
                        "day_high": 334.8,
                        "day_low": 323.2,
                        "volume": 18233000,
                        "status": "ok",
                        "source": "yahoo_finance",
                        "message": None,
                        "fetched_at": "2026-03-16T12:00:00Z",
                        "is_abnormal": True,
                        "abnormal_reason": "price_move",
                    }
                ],
            },
        )
    ]


def test_market_kline_route_returns_chart_payload(monkeypatch) -> None:
    class FakeChartService:
        def get_kline(self, symbol, interval, range_name, session):  # pragma: no cover - exercised through route
            assert symbol == "HK0100"
            assert interval == "1d"
            assert range_name == "6mo"
            return {
                "symbol": "HK0100",
                "interval": "1d",
                "range": "6mo",
                "stale": False,
                "candles": [
                    {
                        "time": "2026-03-20",
                        "open": 995.0,
                        "high": 1048.0,
                        "low": 900.0,
                        "close": 916.5,
                        "volume": 2078996,
                    }
                ],
                "indicators": {
                    "ma5": [{"time": "2026-03-20", "value": 950.2}],
                    "ma10": [],
                    "ma20": [],
                    "ma60": [],
                    "macd": [{"time": "2026-03-20", "dif": 12.3, "dea": 8.7, "histogram": 3.6}],
                    "kdj": [{"time": "2026-03-20", "k": 45.2, "d": 38.1, "j": 59.4}],
                    "bollinger": [{"time": "2026-03-20", "upper": 1050.0, "middle": 980.0, "lower": 910.0}],
                },
                "news_events": [
                    {
                        "time": "2026-03-20",
                        "items": [{"id": 7, "title": "MINIMAX发布新模型", "sentiment": "positive"}],
                    }
                ],
            }

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/HK0100/kline?interval=1d&range=6mo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "HK0100"
    assert payload["candles"][0]["close"] == 916.5
    assert payload["indicators"]["macd"][0]["histogram"] == 3.6
    assert payload["news_events"][0]["items"][0]["id"] == 7
    assert payload["stale"] is False


def test_market_kline_route_returns_a_share_chart_payload(monkeypatch) -> None:
    class FakeChartService:
        def get_kline(self, symbol, interval, range_name, session):  # pragma: no cover - exercised through route
            assert symbol == "600519.SH"
            assert interval == "1d"
            assert range_name == "1y"
            return {
                "symbol": "600519.SH",
                "interval": "1d",
                "range": "1y",
                "stale": False,
                "candles": [
                    {
                        "time": "2026-03-30",
                        "open": 1670.0,
                        "high": 1699.0,
                        "low": 1668.0,
                        "close": 1688.8,
                        "volume": 928000,
                    }
                ],
                "indicators": {
                    "ma5": [{"time": "2026-03-30", "value": 1678.5}],
                    "ma10": [],
                    "ma20": [],
                    "ma60": [],
                    "macd": [{"time": "2026-03-30", "dif": 8.2, "dea": 5.4, "histogram": 2.8}],
                    "kdj": [{"time": "2026-03-30", "k": 61.0, "d": 55.2, "j": 72.6}],
                    "bollinger": [{"time": "2026-03-30", "upper": 1705.0, "middle": 1672.0, "lower": 1639.0}],
                },
                "news_events": [
                    {
                        "time": "2026-03-30",
                        "items": [{"id": 42, "title": "贵州茅台披露经营数据", "sentiment": "positive"}],
                    }
                ],
            }

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/600519.SH/kline?interval=1d&range=1y")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["candles"][0]["close"] == 1688.8
    assert payload["news_events"][0]["items"][0]["id"] == 42


def test_market_kline_route_accepts_bare_a_share_numeric_alias(monkeypatch) -> None:
    class FakeChartService:
        def get_kline(self, symbol, interval, range_name, session):  # pragma: no cover - exercised through route
            assert symbol == "600519"
            assert interval == "1d"
            assert range_name == "1y"
            return {
                "symbol": "600519.SH",
                "interval": "1d",
                "range": "1y",
                "stale": False,
                "candles": [
                    {
                        "time": "2026-03-30",
                        "open": 1670.0,
                        "high": 1699.0,
                        "low": 1668.0,
                        "close": 1688.8,
                        "volume": 928000,
                    }
                ],
                "indicators": {
                    "ma5": [{"time": "2026-03-30", "value": 1678.5}],
                    "ma10": [],
                    "ma20": [],
                    "ma60": [],
                    "macd": [],
                    "kdj": [],
                    "bollinger": [],
                },
                "news_events": [],
            }

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/600519/kline?interval=1d&range=1y")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"


def test_market_kline_route_returns_404_for_non_watchlist_symbol(monkeypatch) -> None:
    from fastapi import HTTPException

    class FakeChartService:
        def get_kline(self, symbol, interval, range_name, session):  # pragma: no cover - exercised through route
            raise HTTPException(status_code=404, detail="watchlist symbol not found")

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.get("/api/market/symbols/AAPL/kline")

    assert response.status_code == 404
    assert response.json()["detail"] == "watchlist symbol not found"


def test_market_sparklines_route_returns_price_map(monkeypatch) -> None:
    class FakeChartService:
        def get_sparklines(self, symbols, session):  # pragma: no cover - exercised through route
            assert symbols == ["HK0100", "600519.SH"]
            return {
                "HK0100": {"prices": [920.0, 935.0, 910.0]},
                "600519.SH": {"prices": [1650.0, 1676.3, 1688.8]},
            }

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.post("/api/market/sparklines", json={"symbols": ["HK0100", "600519.SH"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["HK0100"]["prices"] == [920.0, 935.0, 910.0]
    assert payload["600519.SH"]["prices"][-1] == 1688.8


def test_market_sparklines_route_rejects_more_than_30_symbols(monkeypatch) -> None:
    class FakeChartService:
        def get_sparklines(self, symbols, session):  # pragma: no cover - route validation should fire first
            raise AssertionError("route should reject the payload before service execution")

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.post("/api/market/sparklines", json={"symbols": [f"HK{i:04d}" for i in range(31)]})

    assert response.status_code == 400


def test_market_chart_service_aligns_news_to_previous_trading_day() -> None:
    service = MarketChartService()
    aligned = service._align_news_events(
        candles=[
            {"time": "2026-03-20"},
            {"time": "2026-03-23"},
        ],
        news_items=[
            {
                "id": 1,
                "title": "Weekend note",
                "sentiment_label": "neutral",
                "published_at": "2026-03-22T09:30:00Z",
            },
            {
                "id": 2,
                "title": "Monday open",
                "sentiment_label": "positive",
                "published_at": "2026-03-23T14:00:00Z",
            },
        ],
    )

    assert aligned == [
        {
            "time": "2026-03-20",
            "items": [{"id": 1, "title": "Weekend note", "sentiment": "neutral", "summary": ""}],
        },
        {
            "time": "2026-03-23",
            "items": [{"id": 2, "title": "Monday open", "sentiment": "positive", "summary": ""}],
        },
    ]


def test_market_chart_service_reads_fresh_payload_from_redis_cache() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.storage = {
                "market:kline:HK0100:1d:6mo": '{"symbol":"HK0100","interval":"1d","range":"6mo","stale":false,"candles":[],"indicators":{"ma5":[],"ma10":[],"ma20":[],"ma60":[],"macd":[],"kdj":[],"bollinger":[]},"news_events":[]}'
            }

        def get(self, key: str):
            return self.storage.get(key)

        def set(self, key: str, value: str, ex: int) -> bool:
            self.storage[key] = value
            return True

    service = MarketChartService(redis_client=FakeRedis())

    cached = service._get_cache("market:kline:HK0100:1d:6mo")

    assert cached is not None
    assert cached["symbol"] == "HK0100"


def test_market_chart_service_falls_back_to_memory_cache_when_redis_unavailable() -> None:
    class FailingRedis:
        def get(self, key: str):
            raise RuntimeError("redis unavailable")

        def set(self, key: str, value: str, ex: int) -> bool:
            raise RuntimeError("redis unavailable")

    service = MarketChartService(redis_client=FailingRedis())
    payload = {
        "symbol": "HK0100",
        "interval": "1d",
        "range": "6mo",
        "stale": False,
        "candles": [],
        "indicators": {"ma5": [], "ma10": [], "ma20": [], "ma60": [], "macd": [], "kdj": [], "bollinger": []},
        "news_events": [],
    }

    service._set_cache("market:kline:HK0100:1d:6mo", payload, ttl_seconds=300)

    cached = service._get_cache("market:kline:HK0100:1d:6mo")

    assert cached is not None
    assert cached["symbol"] == "HK0100"


class _NullRedis:
    """get 永远未命中、set 永远成功的 redis 替身,让缓存只走进程内字典。"""

    def get(self, key: str):
        return None

    def set(self, key: str, value: str, ex: int) -> bool:
        return True


def _seed_watchlist_symbol(symbol: str, market: str) -> None:
    with SessionLocal() as session:
        session.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).delete()
        session.add(
            WatchlistItem(
                symbol=symbol,
                market=market,
                display_name=f"{symbol} 测试标的",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.commit()


def _kline_history_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 1100],
        },
        index=pd.to_datetime(["2026-07-16", "2026-07-17"]),
    )


def test_market_chart_service_serves_fresh_kline_from_cache_without_redownload() -> None:
    """TTL 内第二次 get_kline 直接返回缓存,不再触发 yf.download。"""
    symbol = "HK7000"
    _seed_watchlist_symbol(symbol, "hk")
    MarketChartService._cache.pop(f"market:kline:{symbol}:1d:6mo", None)
    service = MarketChartService(redis_client=_NullRedis())

    with patch("yfinance.download", return_value=_kline_history_frame()) as mock_download:
        with SessionLocal() as session:
            first = service.get_kline(symbol, "1d", "6mo", session)
        with SessionLocal() as session:
            second = service.get_kline(symbol, "1d", "6mo", session)

    assert mock_download.call_count == 1
    assert first["symbol"] == symbol
    assert first["stale"] is False
    assert second == first


def test_market_chart_service_returns_stale_cache_when_download_fails() -> None:
    """缓存已过 TTL 且下载失败时,按 stale 兜底返回旧缓存并标记 stale=True。"""
    symbol = "HK7001"
    _seed_watchlist_symbol(symbol, "hk")
    service = MarketChartService(redis_client=_NullRedis())
    payload = {
        "symbol": symbol,
        "interval": "1d",
        "range": "6mo",
        "stale": False,
        "candles": [],
        "indicators": {"ma5": [], "ma10": [], "ma20": [], "ma60": [], "macd": [], "kdj": [], "bollinger": []},
        "news_events": [],
    }
    # ttl 为负 => 写入即过期,模拟"有旧缓存但已过 TTL"。
    service._set_cache(f"market:kline:{symbol}:1d:6mo", payload, ttl_seconds=-1)

    with patch("yfinance.download", side_effect=RuntimeError("yf down")):
        with SessionLocal() as session:
            result = service.get_kline(symbol, "1d", "6mo", session)

    assert result["stale"] is True
    assert result["symbol"] == symbol


def test_news_mentions_repository_list_related_news_applies_limit() -> None:
    """list_related_news 默认/显式 limit 生效,避免无界查询。"""
    from app.models.news_item import NewsItem
    from app.models.news_stock_mention import NewsStockMention
    from app.repositories.news_mentions_repository import NewsMentionsRepository

    symbol = "HK7002"
    with SessionLocal() as session:
        session.query(NewsStockMention).filter(NewsStockMention.symbol == symbol).delete()
        for index in range(3):
            news = NewsItem(
                source_name="Limit Test",
                source_url="https://example.com/limit",
                title=f"Limit test news {index}",
                summary="limit test",
                canonical_url=f"https://example.com/limit-{symbol}-{index}",
                url_hash=f"limit-{symbol}-{index}",
                market="hk",
                language="zh",
                published_at=datetime(2026, 7, 17, 9, index, tzinfo=UTC),
                fetched_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
            )
            session.add(news)
            session.flush()
            session.add(NewsStockMention(news_id=news.id, symbol=symbol, market="hk"))
        session.commit()

        repo = NewsMentionsRepository(session)
        assert len(repo.list_related_news(symbol)) == 3
        assert len(repo.list_related_news(symbol, limit=2)) == 2


def test_market_chart_service_flattens_yfinance_multiindex_history() -> None:
    service = MarketChartService()
    history = pd.DataFrame(
        {
            ("Open", "0700.HK"): [649.5, 658.0],
            ("High", "0700.HK"): [664.5, 666.5],
            ("Low", "0700.HK"): [647.5, 657.5],
            ("Close", "0700.HK"): [660.0, 663.0],
            ("Volume", "0700.HK"): [20489556, 20610633],
        },
        index=pd.to_datetime(["2025-09-29", "2025-09-30"]),
    )

    with patch("yfinance.download", return_value=history):
        normalized = service._download_history("0700.HK", period="6mo", interval="1d")

    candles = service._serialize_candles(normalized)

    assert normalized.columns.tolist() == ["Open", "High", "Low", "Close", "Volume"]
    assert candles == [
        {
            "time": "2025-09-29",
            "open": 649.5,
            "high": 664.5,
            "low": 647.5,
            "close": 660.0,
            "volume": 20489556,
        },
        {
            "time": "2025-09-30",
            "open": 658.0,
            "high": 666.5,
            "low": 657.5,
            "close": 663.0,
            "volume": 20610633,
        },
    ]


def test_market_chart_service_skips_failed_symbols_when_building_sparklines() -> None:
    service = MarketChartService()

    def fake_require(symbol: str, session):
        if symbol == "BAD":
            raise RuntimeError("unsupported symbol")
        item = MagicMock()
        item.symbol = symbol
        item.market = "hk"
        return item

    def fake_download(provider_symbol: str, period: str, interval: str):
        if provider_symbol == "HK0700":
            return MagicMock(__getitem__=lambda self, key: None)
        frame = MagicMock()
        close_series = MagicMock()
        close_series.tail.return_value.dropna.return_value.tolist.return_value = [920.0, 935.0, 910.0]
        frame.__getitem__.return_value = close_series
        return frame

    with patch.object(service, "_require_watchlist_symbol", side_effect=fake_require), patch(
        "app.services.market_chart_service.normalize_symbol",
        side_effect=lambda symbol, market: MagicMock(provider_symbol=symbol),
    ), patch.object(service, "_download_history", side_effect=fake_download):
        payload = service.get_sparklines(["HK0100", "BAD"], session=MagicMock())

    assert payload == {
        "HK0100": {"prices": [920.0, 935.0, 910.0]},
    }


def test_market_chart_service_supports_a_share_sparklines() -> None:
    service = MarketChartService()

    def fake_require(symbol: str, session):
        item = MagicMock()
        item.symbol = symbol
        item.market = "cn"
        return item

    frame = MagicMock()
    close_series = MagicMock()
    close_series.tail.return_value.dropna.return_value.tolist.return_value = [1650.0, 1676.3, 1688.8]
    frame.__getitem__.return_value = close_series

    with patch.object(service, "_require_watchlist_symbol", side_effect=fake_require), patch.object(
        service, "_download_history", return_value=frame
    ):
        payload = service.get_sparklines(["600519.SH"], session=MagicMock())

    assert payload == {
        "600519.SH": {"prices": [1650.0, 1676.3, 1688.8]},
    }


def test_quote_service_has_hot_alert() -> None:
    from datetime import timedelta

    from app.models.news_item import NewsItem
    from app.models.news_stock_mention import NewsStockMention
    service = QuoteService()

    with SessionLocal() as session:
        # 清理数据
        session.query(NewsStockMention).filter(NewsStockMention.symbol == "BABA").delete()
        session.query(WatchlistItem).filter(WatchlistItem.symbol.in_(["BABA", "AAPL"])).delete()
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol.in_(["BABA", "AAPL"])).delete()
        session.commit()

        # 插入 AAPL (无警报)
        session.add(WatchlistItem(symbol="AAPL", market="us", display_name="Apple"))
        session.add(PriceSnapshot(
            symbol="AAPL", market="us", price=150.0, change_percent=0.0, provider_name="test", provider_symbol="AAPL", quote_status="ok", fetched_at=datetime.now(UTC)
        ))

        # 插入 BABA (有警报)
        session.add(WatchlistItem(symbol="BABA", market="us", display_name="Alibaba"))
        session.add(PriceSnapshot(
            symbol="BABA", market="us", price=80.0, change_percent=0.0, provider_name="test", provider_symbol="BABA", quote_status="ok", fetched_at=datetime.now(UTC)
        ))

        # 插入重大新闻 (情绪分0.9, 2小时前)
        news = NewsItem(
            title="Alibaba Big Breakthrough",
            summary="A breakthrough in AI",
            source_name="Reuters",
            source_url="https://reuters.com",
            market="us",
            sentiment_label="positive",
            sentiment_score=0.9,
            url_hash="hash_baba_test_123",
            canonical_url="https://reuters.com/baba_test_123",
            published_at=datetime.now(UTC) - timedelta(hours=2),
            fetched_at=datetime.now(UTC),
        )
        session.add(news)
        session.commit()

        # 插入关联
        session.add(NewsStockMention(news_id=news.id, symbol="BABA", market="us"))
        session.commit()

        # 执行查询
        quotes = service.get_cached_watchlist_quotes(session)

        # 断言
        quotes_map = {q["symbol"]: q for q in quotes}
        assert "BABA" in quotes_map
        assert quotes_map["BABA"]["has_hot_alert"] is True

        assert "AAPL" in quotes_map
        assert quotes_map["AAPL"]["has_hot_alert"] is False

        # 清理
        session.query(NewsStockMention).filter(NewsStockMention.symbol == "BABA").delete()
        session.delete(news)
        session.query(WatchlistItem).filter(WatchlistItem.symbol.in_(["BABA", "AAPL"])).delete()
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol.in_(["BABA", "AAPL"])).delete()
        session.commit()
