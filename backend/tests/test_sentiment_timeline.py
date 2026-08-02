"""个股情绪时间线 API 测试（工作块 G1）：跨日/时区边界聚合、无新闻不补零、
top_news 排序、sentiment_score 缺失过滤、symbol 不在自选股 404、内嵌背离判定。

不联网、不硬编码绝对路径；时区边界断言用 `SHANGHAI_TZ` 现算期望日期而不是写死
字符串，避免依赖测试运行的真实"今天"。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.sentiment_timeline import SHANGHAI_TZ

client = TestClient(app)


def _seed_news(
    session,
    *,
    symbol: str,
    market: str,
    published_at: datetime,
    sentiment_score: float | None,
    sentiment_label: str | None,
    title: str = "test news",
) -> NewsItem:
    url = f"https://example.com/timeline/{uuid.uuid4().hex[:16]}"
    news = NewsItem(
        source_name="test",
        source_url=url,
        title=title,
        summary="summary",
        canonical_url=url,
        url_hash=sha256(url.encode()).hexdigest(),
        market=market,
        language="en",
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        published_at=published_at,
        fetched_at=published_at,
        ingest_status="ingested",
    )
    session.add(news)
    session.flush()
    session.add(
        NewsStockMention(news_id=news.id, symbol=symbol, market=market, mention_type="manual", confidence=0.9)
    )
    session.flush()
    return news


def _ensure_watchlist_item(session, *, symbol: str, market: str, display_name: str) -> None:
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is None:
        session.add(
            WatchlistItem(
                symbol=symbol,
                market=market,
                display_name=display_name,
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.flush()


def _save_snapshot(session, *, symbol: str, market: str, price: float, fetched_at: datetime) -> None:
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


def _cleanup_symbol_data(session, symbol: str) -> None:
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


def test_sentiment_timeline_404_for_symbol_not_in_watchlist() -> None:
    resp = client.get("/api/watchlist/NOT-IN-WATCHLIST-XYZ/sentiment-timeline")
    assert resp.status_code == 404


def test_sentiment_timeline_aggregates_across_shanghai_day_boundary_and_skips_missing_score() -> None:
    symbol = "TLBOUND"
    now = datetime.now(UTC)
    # 相距 240h（10 天）以内且都在默认 30 天窗口内，几乎必然落在两个不同的
    # Asia/Shanghai 自然日（除非精确对齐 24h 倍数——概率可忽略）。
    older = now - timedelta(hours=240)
    newer = now - timedelta(hours=4)
    day_older = older.astimezone(SHANGHAI_TZ).date().isoformat()
    day_newer = newer.astimezone(SHANGHAI_TZ).date().isoformat()
    assert day_older != day_newer, "test fixture picked offsets that collide on the same Shanghai day"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Timeline Bound Test")
        _seed_news(session, symbol=symbol, market="us", published_at=older, sentiment_score=0.9, sentiment_label="positive", title="Old Positive")
        _seed_news(session, symbol=symbol, market="us", published_at=older + timedelta(minutes=5), sentiment_score=-0.2, sentiment_label="negative", title="Old Negative")
        _seed_news(session, symbol=symbol, market="us", published_at=newer, sentiment_score=0.5, sentiment_label="positive", title="Recent Positive")
        # 无情绪分数的新闻不应参与聚合。
        _seed_news(session, symbol=symbol, market="us", published_at=newer, sentiment_score=None, sentiment_label=None, title="No Score")
        session.commit()

    resp = client.get(f"/api/watchlist/{symbol}/sentiment-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == symbol
    assert data["days"] == 30

    points_by_date = {p["date"]: p for p in data["points"]}
    assert set(points_by_date.keys()) == {day_older, day_newer}

    older_point = points_by_date[day_older]
    assert older_point["news_count"] == 2
    assert older_point["positive_count"] == 1
    assert older_point["negative_count"] == 1
    assert abs(older_point["avg_score"] - 0.35) < 1e-9

    newer_point = points_by_date[day_newer]
    assert newer_point["news_count"] == 1
    assert newer_point["positive_count"] == 1

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_sentiment_timeline_top_news_sorted_by_abs_score_desc_capped_at_3() -> None:
    symbol = "TLTOPN"
    published_at = datetime.now(UTC) - timedelta(hours=3)

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Top News Test")
        _seed_news(session, symbol=symbol, market="us", published_at=published_at, sentiment_score=0.1, sentiment_label="neutral", title="Weakest")
        _seed_news(session, symbol=symbol, market="us", published_at=published_at, sentiment_score=-0.9, sentiment_label="negative", title="Strongest Negative")
        _seed_news(session, symbol=symbol, market="us", published_at=published_at, sentiment_score=0.5, sentiment_label="positive", title="Second Strongest")
        _seed_news(session, symbol=symbol, market="us", published_at=published_at, sentiment_score=-0.3, sentiment_label="negative", title="Third Strongest")
        session.commit()

    resp = client.get(f"/api/watchlist/{symbol}/sentiment-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) == 1
    top_news = data["points"][0]["top_news"]
    assert [n["title"] for n in top_news] == ["Strongest Negative", "Second Strongest", "Third Strongest"]
    assert len(top_news) == 3

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_sentiment_timeline_no_news_dates_are_not_zero_filled() -> None:
    symbol = "TLSPARSE"
    published_at = datetime.now(UTC) - timedelta(hours=5)

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Sparse Test")
        _seed_news(session, symbol=symbol, market="us", published_at=published_at, sentiment_score=0.2, sentiment_label="positive", title="Only News")
        session.commit()

    resp = client.get(f"/api/watchlist/{symbol}/sentiment-timeline?days=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["days"] == 10
    assert len(data["points"]) == 1

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_sentiment_timeline_embeds_bearish_divergence_when_thresholds_crossed() -> None:
    symbol = "TLDIVBR"
    now = datetime.now(UTC)

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Divergence Test")
        for i in range(4):
            _seed_news(
                session,
                symbol=symbol,
                market="us",
                published_at=now - timedelta(hours=i + 1),
                sentiment_score=0.7,
                sentiment_label="positive",
                title=f"Bullish news {i}",
            )
        _save_snapshot(session, symbol=symbol, market="us", price=100.0, fetched_at=now - timedelta(days=2))
        _save_snapshot(session, symbol=symbol, market="us", price=90.0, fetched_at=now)
        session.commit()

    resp = client.get(f"/api/watchlist/{symbol}/sentiment-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence"] is not None
    assert data["divergence"]["status"] == "bearish_divergence"
    assert data["divergence"]["news_count"] == 4
    assert abs(data["divergence"]["sentiment_avg"] - 0.7) < 1e-9
    assert data["divergence"]["price_change_percent"] < 0

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_sentiment_timeline_divergence_null_when_insufficient_samples() -> None:
    symbol = "TLDIVNONE"
    now = datetime.now(UTC)

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="No Divergence Test")
        # 只有 2 条新闻，样本不足（阈值 3），不判定背离。
        _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(hours=1), sentiment_score=0.8, sentiment_label="positive")
        _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(hours=2), sentiment_score=0.6, sentiment_label="positive")
        session.commit()

    resp = client.get(f"/api/watchlist/{symbol}/sentiment-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence"] is None

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_sentiment_timeline_days_and_window_query_bounds_enforced() -> None:
    symbol = "TLBOUNDQ"
    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Bounds Test")
        session.commit()

    assert client.get(f"/api/watchlist/{symbol}/sentiment-timeline?days=91").status_code == 422
    assert client.get(f"/api/watchlist/{symbol}/sentiment-timeline?days=0").status_code == 422
    assert client.get(f"/api/watchlist/{symbol}/sentiment-timeline?window=15").status_code == 422
    assert client.get(f"/api/watchlist/{symbol}/sentiment-timeline?window=0").status_code == 422
    ok = client.get(f"/api/watchlist/{symbol}/sentiment-timeline?days=90&window=14")
    assert ok.status_code == 200

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()
