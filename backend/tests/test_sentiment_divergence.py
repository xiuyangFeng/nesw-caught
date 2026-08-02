"""情绪-价格背离检测服务测试（工作块 G2）：多空方向、样本不足、快照不足、阈值边界。

全部通过 monkeypatch 覆盖 `app.services.sentiment_divergence.get_settings`，固定
阈值/窗口，不依赖 config.py 的默认值漂移；不联网。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.services import sentiment_divergence as sentiment_divergence_module
from app.services.sentiment_divergence import detect_divergence

TEST_SETTINGS = Settings(
    sentiment_divergence_alert_enabled=False,
    sentiment_divergence_window_days=3,
    sentiment_divergence_min_abs_sentiment=0.4,
    sentiment_divergence_min_abs_price_change_percent=3.0,
)


def _use_fixed_settings(monkeypatch, settings: Settings = TEST_SETTINGS) -> None:
    monkeypatch.setattr(sentiment_divergence_module, "get_settings", lambda: settings)


def _seed_news(session, *, symbol: str, market: str, published_at: datetime, sentiment_score: float) -> None:
    url = f"https://example.com/divergence/{uuid.uuid4().hex[:16]}"
    news = NewsItem(
        source_name="test",
        source_url=url,
        title="divergence test news",
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


def _cleanup(session, symbol: str) -> None:
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


def _seed_standard_scenario(session, symbol: str, *, sentiment_scores: list[float], prices: list[float]) -> None:
    now = datetime.now(UTC)
    for idx, score in enumerate(sentiment_scores):
        _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(hours=idx + 1), sentiment_score=score)
    if prices:
        span = timedelta(days=2)
        step = span / max(len(prices) - 1, 1)
        for idx, price in enumerate(prices):
            _seed_snapshot(session, symbol=symbol, market="us", price=price, fetched_at=now - span + step * idx)


def test_bearish_divergence_when_sentiment_hot_and_price_falls(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVBR01"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.6, 0.7, 0.5], prices=[100.0, 95.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is not None
        assert result.status == "bearish_divergence"
        assert result.news_count == 3
        assert result.window_days == 3
        assert result.price_change_percent < 0

        _cleanup(session, symbol)
        session.commit()


def test_bullish_divergence_when_sentiment_cold_and_price_rises(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVBL01"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        _seed_standard_scenario(session, symbol, sentiment_scores=[-0.6, -0.7, -0.5], prices=[100.0, 106.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is not None
        assert result.status == "bullish_divergence"
        assert result.price_change_percent > 0

        _cleanup(session, symbol)
        session.commit()


def test_none_when_news_count_below_minimum(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVTHIN"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 只有 2 条新闻，低于 MIN_NEWS_COUNT_FOR_SENTIMENT=3。
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.9, 0.8], prices=[100.0, 90.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is None

        _cleanup(session, symbol)
        session.commit()


def test_none_when_price_snapshots_insufficient(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVNOSNAP"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 情绪样本充足，但只有 1 条（甚至 0 条）价格快照。
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.9, 0.8, 0.7], prices=[100.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is None

        _cleanup(session, symbol)
        session.commit()


def test_none_when_sentiment_and_price_move_in_same_direction(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVALIGN"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 情绪偏多、价格同步上涨——正常一致，不是背离。
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.6, 0.7, 0.5], prices=[100.0, 106.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is None

        _cleanup(session, symbol)
        session.commit()


def test_none_when_below_threshold_boundary(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVBELOW"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 情绪均值 0.35 < 阈值 0.4；价格跌幅 5% 越过阈值，但情绪没过 —— 不判定。
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.3, 0.4, 0.35], prices=[100.0, 95.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is None

        _cleanup(session, symbol)
        session.commit()


def test_boundary_values_are_inclusive(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVEDGE"
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 情绪均值恰好 0.4（>= 阈值），价格跌幅恰好 3.0%（<= -阈值）—— 边界应判定为背离。
        _seed_standard_scenario(session, symbol, sentiment_scores=[0.4, 0.4, 0.4], prices=[100.0, 97.0])
        session.commit()

        result = detect_divergence(symbol, None, session)
        assert result is not None
        assert result.status == "bearish_divergence"

        _cleanup(session, symbol)
        session.commit()


def test_window_days_param_overrides_settings_default_and_is_clamped(monkeypatch) -> None:
    _use_fixed_settings(monkeypatch)
    symbol = "DIVWIN"
    now = datetime.now(UTC)
    with SessionLocal() as session:
        _cleanup(session, symbol)
        # 新闻在 5 天前——默认窗口 3 天看不到，显式传 window=7 才能覆盖到。
        for idx, score in enumerate([0.6, 0.7, 0.5]):
            _seed_news(session, symbol=symbol, market="us", published_at=now - timedelta(days=5, hours=idx), sentiment_score=score)
        _seed_snapshot(session, symbol=symbol, market="us", price=100.0, fetched_at=now - timedelta(days=6))
        _seed_snapshot(session, symbol=symbol, market="us", price=90.0, fetched_at=now)
        session.commit()

        assert detect_divergence(symbol, None, session) is None
        assert detect_divergence(symbol, 3, session) is None

        result = detect_divergence(symbol, 7, session)
        assert result is not None
        assert result.window_days == 7
        assert result.status == "bearish_divergence"

        # 越界的 window 会被夹紧到 [1, 14]。
        clamped = detect_divergence(symbol, 999, session)
        assert clamped is not None
        assert clamped.window_days == 14

        _cleanup(session, symbol)
        session.commit()
