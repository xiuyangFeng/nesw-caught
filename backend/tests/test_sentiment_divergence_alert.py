"""情绪-价格背离提醒接入通知测试（工作块 G3）。

覆盖：飞书卡片构造、`NotificationService.on_sentiment_divergence_detected` 的
入队与同日去重、`_build_card_for_job` 分支、`SentimentDivergenceAlertWorker`
在关闭/开启开关下的行为、`NotificationService.start()` 按
`settings.sentiment_divergence_alert_enabled` 惰性起停周期 worker（验证不用改
main.py 也能接入）。全程不联网、不硬编码绝对路径。
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import app
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.notification_job import NotificationJob
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.feishu_client import build_sentiment_divergence_card
from app.services.notification_service import NotificationService
from app.workers import queue_worker as queue_worker_module
from app.workers.queue_worker import SentimentDivergenceAlertWorker

client = TestClient(app)

VALID_CONFIG = {
    "app_id": "cli_test_divergence",
    "app_secret": "secret_divergence",
    "target_type": "chat",
    "target_id": "oc_test_divergence_chat",
    "news_enabled": False,
    "alert_enabled": False,
    "analysis_enabled": False,
    "news_batch_interval_minutes": 30,
    "is_active": True,
}


def _create_config(**overrides):
    payload = dict(VALID_CONFIG)
    payload.update(overrides)
    resp = client.post("/api/notify/feishu/config", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _clean_state(symbol: str | None = None) -> None:
    with SessionLocal() as session:
        session.query(NotificationJob).delete()
        session.query(FeishuNotifyConfig).delete()
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


def _load_jobs(event_type: str | None = None) -> list[NotificationJob]:
    with SessionLocal() as session:
        jobs = session.query(NotificationJob).order_by(NotificationJob.id.asc()).all()
    if event_type is not None:
        return [job for job in jobs if job.event_type == event_type]
    return jobs


def _job_payload(job: NotificationJob) -> dict:
    return json.loads(job.payload_json)


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
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        for idx, score in enumerate([0.6, 0.7, 0.5]):
            _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(hours=idx + 1), sentiment_score=score)
        _seed_snapshot(session, symbol=symbol, market="us", price=100.0, fetched_at=now - timedelta(days=2))
        _seed_snapshot(session, symbol=symbol, market="us", price=90.0, fetched_at=now)
        session.commit()


def test_build_sentiment_divergence_card_bearish() -> None:
    card = build_sentiment_divergence_card(
        symbol="AAPL",
        display_name="Apple",
        status="bearish_divergence",
        window_days=3,
        sentiment_avg=0.65,
        price_change_percent=-5.2,
    )
    assert "Apple" in card["header"]["title"]["content"]
    assert card["header"]["template"] == "red"
    fields_text = json.dumps(card, ensure_ascii=False)
    assert "AAPL" in fields_text
    assert "0.65" in fields_text or "+0.65" in fields_text
    assert "-5.20%" in fields_text


def test_build_sentiment_divergence_card_bullish() -> None:
    card = build_sentiment_divergence_card(
        symbol="0700.HK",
        display_name="Tencent",
        status="bullish_divergence",
        window_days=5,
        sentiment_avg=-0.5,
        price_change_percent=4.1,
    )
    assert card["header"]["template"] == "green"
    assert "Tencent" in card["header"]["title"]["content"]


def test_on_sentiment_divergence_detected_enqueues_job_with_normal_severity_and_dedupes_same_day() -> None:
    _clean_state()
    _create_config()
    service = NotificationService()

    payload = {
        "symbol": "AAPL",
        "display_name": "Apple",
        "market": "us",
        "status": "bearish_divergence",
        "window_days": 3,
        "sentiment_avg": 0.65,
        "news_count": 4,
        "price_change_percent": -5.2,
        "detected_at": datetime.now(UTC).isoformat(),
    }
    service.on_sentiment_divergence_detected(payload)
    service.on_sentiment_divergence_detected(dict(payload))  # 同日重复命中：应被去重，不产生第二条

    jobs = _load_jobs("sentiment_divergence")
    assert len(jobs) == 1
    assert jobs[0].channel == "feishu"
    assert _job_payload(jobs[0])["symbol"] == "AAPL"
    assert service._classify_severity("sentiment_divergence", payload) == "normal"

    _clean_state()


def test_on_sentiment_divergence_detected_noop_without_active_feishu_config() -> None:
    _clean_state()
    service = NotificationService()

    service.on_sentiment_divergence_detected(
        {
            "symbol": "AAPL",
            "status": "bearish_divergence",
            "detected_at": datetime.now(UTC).isoformat(),
        }
    )

    assert _load_jobs("sentiment_divergence") == []
    _clean_state()


def test_build_card_for_job_dispatches_sentiment_divergence_event() -> None:
    _clean_state()
    _create_config()
    service = NotificationService()

    service.on_sentiment_divergence_detected(
        {
            "symbol": "AAPL",
            "display_name": "Apple",
            "status": "bearish_divergence",
            "window_days": 3,
            "sentiment_avg": 0.6,
            "price_change_percent": -4.0,
            "detected_at": datetime.now(UTC).isoformat(),
        }
    )
    job = _load_jobs("sentiment_divergence")[0]
    card = service._build_card_for_job(job)
    assert card is not None
    assert "Apple" in card["header"]["title"]["content"]

    _clean_state()


def test_worker_do_cycle_enqueues_when_divergence_detected() -> None:
    symbol = "DIVWORKER"
    _clean_state(symbol)
    _create_config()
    _seed_bearish_divergence_watchlist_item(symbol)

    service = NotificationService()
    worker = SentimentDivergenceAlertWorker(session_factory=SessionLocal, notification_service=service)

    hits = worker.do_cycle()
    assert hits >= 1

    jobs = _load_jobs("sentiment_divergence")
    matching = [job for job in jobs if _job_payload(job)["symbol"] == symbol]
    assert len(matching) == 1
    assert _job_payload(matching[0])["status"] == "bearish_divergence"

    # 第二次周期同日再次命中同一 symbol/方向：治理去重生效，不产生第二条 job。
    worker.do_cycle()
    jobs_after = _load_jobs("sentiment_divergence")
    matching_after = [job for job in jobs_after if _job_payload(job)["symbol"] == symbol]
    assert len(matching_after) == 1

    _clean_state(symbol)


def test_worker_do_cycle_produces_no_jobs_when_no_divergence() -> None:
    symbol = "DIVWORKERNONE"
    _clean_state(symbol)
    _create_config()
    with SessionLocal() as session:
        session.add(
            WatchlistItem(
                symbol=symbol,
                market="us",
                display_name="No Divergence Co",
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.commit()

    service = NotificationService()
    worker = SentimentDivergenceAlertWorker(session_factory=SessionLocal, notification_service=service)

    hits = worker.do_cycle()
    assert hits == 0
    assert _load_jobs("sentiment_divergence") == []

    _clean_state(symbol)


def test_notification_service_start_skips_divergence_worker_when_flag_disabled(monkeypatch) -> None:
    from app.services import notification_service as notification_service_module

    disabled_settings = Settings(sentiment_divergence_alert_enabled=False)
    monkeypatch.setattr(notification_service_module, "get_settings", lambda: disabled_settings)

    service = NotificationService(poll_interval_seconds=1)
    service.start()
    try:
        assert service._divergence_worker is None
    finally:
        service.stop()


def test_notification_service_start_creates_divergence_worker_when_flag_enabled(monkeypatch) -> None:
    from app.services import notification_service as notification_service_module

    enabled_settings = Settings(sentiment_divergence_alert_enabled=True)
    monkeypatch.setattr(notification_service_module, "get_settings", lambda: enabled_settings)

    service = NotificationService(poll_interval_seconds=1)
    service.start()
    try:
        assert service._divergence_worker is not None
        assert isinstance(service._divergence_worker, queue_worker_module.SentimentDivergenceAlertWorker)
    finally:
        service.stop()
        assert service._divergence_worker is None
