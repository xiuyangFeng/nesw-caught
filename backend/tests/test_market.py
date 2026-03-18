from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.api.routes import market as market_routes
from app.main import app


def test_market_watchlist_quotes_return_expanded_fields(monkeypatch) -> None:
    class FakeQuoteService:
        def get_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
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


def test_market_symbol_detail_normalizes_hk_alias(monkeypatch) -> None:
    class FakeQuoteService:
        def __init__(self) -> None:
            self.received_symbol: str | None = None

        def get_symbol_quote(self, symbol, session):  # pragma: no cover - exercised through route
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


def test_market_watchlist_quotes_keep_partial_failures_visible(monkeypatch) -> None:
    class FakeQuoteService:
        def get_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
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

        def get_watchlist_quotes(self, session):  # pragma: no cover - exercised through route
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

    notification_service = NotificationService()
    notification_service._send = MagicMock(return_value=True)
    config = MagicMock()
    config.alert_enabled = True
    fake_service = FakeQuoteService()
    monkeypatch.setattr(market_routes, "get_quote_service", lambda: fake_service, raising=False)
    monkeypatch.setattr(market_routes, "WatchlistRepository", FakeWatchlistRepository)
    monkeypatch.setattr(market_routes, "get_notification_service", lambda: notification_service)
    client = TestClient(app)

    with patch.object(notification_service, "_load_config", return_value=config):
        response1 = client.get("/api/market/watchlist")
        response2 = client.get("/api/market/watchlist")
        response3 = client.get("/api/market/watchlist")
        response4 = client.get("/api/market/watchlist")

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response3.status_code == 200
    assert response4.status_code == 200
    assert notification_service._send.call_count == 2
