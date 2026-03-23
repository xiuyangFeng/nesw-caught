from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.api.routes import market as market_routes
from app.main import app
from app.services.market_chart_service import MarketChartService


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

    notification_service = NotificationService()
    notification_service._send = MagicMock(return_value=True)
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

    assert notification_service._send.call_count == 2


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
            assert symbols == ["HK0100", "HK0700"]
            return {
                "HK0100": {"prices": [920.0, 935.0, 910.0]},
                "HK0700": {"prices": [500.0, 498.0, 502.0]},
            }

    monkeypatch.setattr(market_routes, "get_market_chart_service", lambda: FakeChartService(), raising=False)
    client = TestClient(app)

    response = client.post("/api/market/sparklines", json={"symbols": ["HK0100", "HK0700"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["HK0100"]["prices"] == [920.0, 935.0, 910.0]
    assert payload["HK0700"]["prices"][-1] == 502.0


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
            "items": [{"id": 1, "title": "Weekend note", "sentiment": "neutral"}],
        },
        {
            "time": "2026-03-23",
            "items": [{"id": 2, "title": "Monday open", "sentiment": "positive"}],
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
