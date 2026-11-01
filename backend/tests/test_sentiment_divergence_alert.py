"""情绪-价格背离提醒测试（情绪模块 Phase 3 · G3，聚焦改造 P2 改为站内提醒）。

覆盖：`SentimentDivergenceAlertWorker.do_cycle` 发现背离后经 `AlertService.on_sentiment_divergence`
写入 `alert` 表（同日同方向去重），以及无背离时不写入。功能开关
`sentiment_divergence_alert_enabled` 默认关闭，由 `app/main.py` lifespan 决定是否启动该 worker。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.alert_service import AlertService
from app.workers.queue_worker import SentimentDivergenceAlertWorker


class _NoopBus:
    def publish(self, event: str, payload: dict) -> None:
        del event, payload


def _alert_service() -> AlertService:
    # 关闭静默时段，避免测试结果依赖运行时刻。
    return AlertService(session_factory=SessionLocal, event_bus=_NoopBus(), quiet_hours=("00:00", "00:00"))


def _clean_state(symbol: str | None = None) -> None:
    with SessionLocal() as session:
        session.query(Alert).filter(Alert.kind == "sentiment_divergence").delete()
        if symbol:
            news_items = list(
                session.scalars(
                    select(NewsItem).join(NewsStockMention, NewsStockMention.news_id == NewsItem.id).where(NewsStockMention.symbol == symbol)
                )
            )
            for news in news_items:
                for mention in session.scalars(select(NewsStockMention).where(NewsStockMention.news_id == news.id)):
                    session.delete(mention)
                session.flush()
                session.delete(news)
            for snapshot in session.scalars(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol)):
                session.delete(snapshot)
            item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
            if item is not None:
                session.delete(item)
        session.commit()



def _load_divergence_alerts(symbol: str) -> list[Alert]:
    with SessionLocal() as session:
        return list(
            session.scalars(
                select(Alert).where(Alert.kind == "sentiment_divergence", Alert.symbol == symbol).order_by(Alert.id)
            )
        )


def _seed_news(session, *, symbol: str, market: str, published_at: datetime, sentiment_score: float) -> None:
    url = f"https://example.com/divergence-alert/{uuid.uuid4().hex[:16]}"
    news = NewsItem(
        source_name="test",
        source_url=url,
        title="divergence alert test news",
        summary=None,
        canonical_url=url,
        url_hash=sha256(url.encode()).hexdigest(),
        market=market,
        language="en",
        sentiment_label="positive" if sentiment_score >= 0 else "negative",
        sentiment_score=sentiment_score,
        published_at=published_at,
        fetched_at=published_at,
        ingest_status="ingested",
    )
    session.add(news)
    session.flush()
    session.add(NewsStockMention(news_id=news.id, symbol=symbol, market=market, mention_type="manual", confidence=0.9))
    session.flush()


def _seed_snapshot(session, *, symbol: str, market: str, price: float, fetched_at: datetime) -> None:
    session.add(
        PriceSnapshot(
            symbol=symbol,
            market=market,
            price=price,
            change_amount=None,
            change_percent=None,
            open_price=None,
            previous_close=None,
            day_high=None,
            day_low=None,
            volume=None,
            provider_name="test",
            provider_symbol=symbol,
            quote_status="ok",
            status_message=None,
            fetched_at=fetched_at,
        )
    )
    session.flush()


def _seed_bearish_divergence_watchlist_item(symbol: str) -> None:
    now = datetime.now(UTC)
    with SessionLocal() as session:
        session.add(
            WatchlistItem(
                symbol=symbol,
                market="us",
                display_name="Divergence Alert Test Co",
                is_active=True,
            )
        )
        for idx, score in enumerate([0.6, 0.7, 0.5]):
            _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(hours=idx + 1), sentiment_score=score)
        _seed_snapshot(session, symbol=symbol, market="us", price=100.0, fetched_at=now - timedelta(days=2))
        _seed_snapshot(session, symbol=symbol, market="us", price=90.0, fetched_at=now)
        session.commit()



def test_worker_do_cycle_writes_alert_when_divergence_detected() -> None:
    symbol = "DIVWORKER"
    _clean_state(symbol)
    _seed_bearish_divergence_watchlist_item(symbol)

    worker = SentimentDivergenceAlertWorker(session_factory=SessionLocal, alert_service=_alert_service())

    hits = worker.do_cycle()
    assert hits >= 1

    alerts = _load_divergence_alerts(symbol)
    assert len(alerts) == 1
    assert json.loads(alerts[0].payload_json)["status"] == "bearish_divergence"

    # 同日再次命中同一 symbol/方向：按 dedupe_key 去重，不产生第二条提醒。
    worker.do_cycle()
    assert len(_load_divergence_alerts(symbol)) == 1

    _clean_state(symbol)


def test_worker_do_cycle_writes_nothing_when_no_divergence() -> None:
    symbol = "DIVWORKERNONE"
    _clean_state(symbol)
    with SessionLocal() as session:
        session.add(
            WatchlistItem(
                symbol=symbol,
                market="us",
                display_name="No Divergence Co",
                is_active=True,
            )
        )
        session.commit()

    worker = SentimentDivergenceAlertWorker(session_factory=SessionLocal, alert_service=_alert_service())

    assert worker.do_cycle() == 0
    assert _load_divergence_alerts(symbol) == []

    _clean_state(symbol)
