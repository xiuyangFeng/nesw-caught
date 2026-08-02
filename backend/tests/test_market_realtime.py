"""行情实时性回归测试。

覆盖 2026-07-27 修复的四层断链：

1. ``refresh_watchlist_quotes`` 被 ``market_quote_cache_ttl_seconds``（180s）短路，
   导致 producer 每 15s 的轮询里有 11 次是空转，真实价格最快 3 分钟才更新一次。
2. ``/api/stream/events`` 不转发 ``market.watchlist_refreshed``，行情永远推不到前端。
3. 该事件的 payload 含 ``datetime``（fetched_at），裸 ``json.dumps`` 会抛 TypeError
   直接打断 SSE 连接。
4. 全市场闭市时 producer 仍按盘中频率空转打 provider。
"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.db.session import SessionLocal
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.market_quote_producer import MarketQuoteProducer
from app.services.quote_provider import QuoteRecord
from app.services.quote_service import QuoteService

SYMBOL = "AAPL"


def _reset_symbol(session) -> None:
    session.query(PriceSnapshot).filter(PriceSnapshot.symbol == SYMBOL).delete()
    item = session.query(WatchlistItem).filter(WatchlistItem.symbol == SYMBOL).one_or_none()
    if item is not None:
        session.delete(item)
    session.commit()


def _seed(session, *, fetched_age_seconds: float) -> None:
    _reset_symbol(session)
    session.add(
        WatchlistItem(
            symbol=SYMBOL,
            market="us",
            display_name="Apple",
            is_active=True,
            alert_threshold=None,
            alert_mode="fixed",
        )
    )
    session.add(
        PriceSnapshot(
            symbol=SYMBOL,
            market="us",
            price=200.0,
            change_amount=1.0,
            change_percent=0.5,
            open_price=199.0,
            previous_close=199.0,
            day_high=201.0,
            day_low=198.0,
            volume=1000,
            provider_name="yahoo_finance",
            provider_symbol=SYMBOL,
            quote_status="ok",
            status_message=None,
            fetched_at=datetime.now(UTC) - timedelta(seconds=fetched_age_seconds),
        )
    )
    session.commit()


def _ok_record(price: float) -> QuoteRecord:
    return QuoteRecord(
        symbol=SYMBOL,
        market="us",
        provider_symbol=SYMBOL,
        price=price,
        change_amount=2.0,
        change_percent=1.0,
        open_price=199.0,
        previous_close=199.0,
        day_high=price,
        day_low=198.0,
        volume=2000,
        source="yahoo_finance",
        status="ok",
        message=None,
        fetched_at=datetime.now(UTC),
    )


def _requested_symbols(batch_mock) -> set[str]:
    """被真正送去联网抓取的标的集合。

    断言只针对本用例的 SYMBOL：测试库里可能残留其它用例的自选股行，用
    ``call_count`` 判定会被它们干扰。
    """
    requested: set[str] = set()
    for call in batch_mock.call_args_list:
        for normalized in call.args[0]:
            requested.add(normalized.symbol)
    return requested


def test_refresh_with_force_refetches_inside_cache_ttl() -> None:
    """force=True 必须绕过 180s 缓存 TTL —— 这是"3 分钟才更新一次"的直接根因。"""
    service = QuoteService()

    with SessionLocal() as session:
        # 30s 前抓过：在 180s TTL 内，非 force 路径会直接吃缓存。
        _seed(session, fetched_age_seconds=30)

        with patch.object(
            service.provider, "fetch_quotes_batch", return_value=[_ok_record(222.0)]
        ) as batch:
            payload = service.refresh_watchlist_quotes(session, force=True)

        assert SYMBOL in _requested_symbols(batch), "force 刷新必须真的联网抓取，而不是吃 180s 缓存"
        row = next(item for item in payload if item["symbol"] == SYMBOL)
        assert row["price"] == 222.0

        _reset_symbol(session)


def test_refresh_without_force_still_uses_cache_ttl() -> None:
    """非 force 的读路径保持既有语义，避免按需抓取被放大成每请求一次外网调用。"""
    service = QuoteService()

    with SessionLocal() as session:
        _seed(session, fetched_age_seconds=30)

        with patch.object(service.provider, "fetch_quotes_batch", return_value=[]) as batch:
            payload = service.refresh_watchlist_quotes(session)

        assert SYMBOL not in _requested_symbols(batch)
        row = next(item for item in payload if item["symbol"] == SYMBOL)
        assert row["price"] == 200.0

        _reset_symbol(session)


def test_force_refresh_still_throttled_by_min_interval() -> None:
    """force 也要有下限：刷新按钮被连点时不能每次都打 provider。"""
    service = QuoteService()

    with SessionLocal() as session:
        # 刚抓过 1s，低于 market_quote_force_min_interval_seconds 默认 5s。
        _seed(session, fetched_age_seconds=1)

        with patch.object(service.provider, "fetch_quotes_batch", return_value=[]) as batch:
            service.refresh_watchlist_quotes(session, force=True)

        assert SYMBOL not in _requested_symbols(batch)

        _reset_symbol(session)


def test_producer_cycle_forces_refresh() -> None:
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    quote_service = MagicMock()
    quote_service.refresh_watchlist_quotes.return_value = []

    producer = MarketQuoteProducer(
        session_factory=session_factory,
        quote_service_factory=lambda: quote_service,
        event_bus=MagicMock(),
        poll_interval_seconds=5.0,
    )
    producer.run_cycle()

    quote_service.refresh_watchlist_quotes.assert_called_once_with(session, force=True)


def test_producer_backs_off_when_all_markets_closed() -> None:
    producer = MarketQuoteProducer(
        session_factory=MagicMock(),
        quote_service_factory=MagicMock(),
        event_bus=MagicMock(),
        poll_interval_seconds=15.0,
        idle_poll_interval_seconds=120.0,
    )

    with patch("app.services.market_quote_producer.any_market_open", return_value=True):
        assert producer.get_interval() == 15.0
    with patch("app.services.market_quote_producer.any_market_open", return_value=False):
        assert producer.get_interval() == 120.0


def test_stream_events_forwards_market_refresh_with_datetime_payload(monkeypatch) -> None:
    """SSE 必须转发行情事件，且 datetime 字段不能打断连接。"""
    from app.api.routes import stream as stream_route

    class FakeRequest:
        async def is_disconnected(self) -> bool:
            return False

    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}
            self.ready = threading.Event()

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)
            if "market.watchlist_refreshed" in self.handlers:
                self.ready.set()

        def unsubscribe(self, event_name: str, handler) -> None:
            self.handlers[event_name] = [
                item for item in self.handlers.get(event_name, []) if item is not handler
            ]

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    fake_bus = FakeBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: fake_bus)

    response = asyncio.run(stream_route.stream_events(FakeRequest(), limit=1))
    fetched_at = datetime(2026, 7, 27, 1, 30, tzinfo=UTC)
    publisher = threading.Thread(
        target=lambda: (
            fake_bus.ready.wait(2),
            fake_bus.publish(
                "market.watchlist_refreshed",
                {
                    "symbols": [SYMBOL],
                    "quotes": [{"symbol": SYMBOL, "price": 222.0, "fetched_at": fetched_at}],
                },
            ),
        ),
        daemon=True,
    )
    publisher.start()

    async def _collect() -> str:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(_collect())
    publisher.join(timeout=1)

    assert '"type":"market.watchlist_refreshed"' in body
    envelope = json.loads(body.split("data: ", 1)[1].strip())
    assert envelope["payload"]["quotes"][0]["price"] == 222.0
    # datetime 被序列化成 ISO 字符串，而不是让 json.dumps 抛 TypeError 断流。
    assert envelope["payload"]["quotes"][0]["fetched_at"].startswith("2026-07-27T01:30:00")


def test_stream_serializes_naive_db_timestamps_as_utc() -> None:
    """naive datetime 必须按 UTC ``replace`` 而不是 ``astimezone``。

    payload 里的 ``fetched_at`` 直接来自 SQLite，是 naive 的 UTC 值。若用
    ``astimezone`` 会把它按本机时区解读——实测在 UTC-7 的机器上把时间戳整体推后
    7 小时，前端"最后更新时间"和 isStale 判定会一起错乱，而且同一个值在 REST
    与 SSE 两条通道上给出不同结果。
    """
    from app.api.routes import stream as stream_route

    naive_utc = datetime(2026, 7, 27, 16, 45, 47, 296680)
    assert stream_route._json_default(naive_utc) == "2026-07-27T16:45:47.296680Z"

    aware = naive_utc.replace(tzinfo=UTC)
    assert stream_route._json_default(aware) == stream_route._json_default(naive_utc)
