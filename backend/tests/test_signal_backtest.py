"""信号有效性回测服务测试（TDD）。

覆盖：命中率 / 平均前视收益 / importance 分桶 / 样本计数，以及
price_snapshot 稀疏时（基准价或前视价缺失）的优雅降级与 skipped 计数。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_signal_result import NewsSignalResult
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.services.signal_backtest import SignalBacktestService


def _clean() -> None:
    with SessionLocal() as session:
        session.query(NewsStockMention).delete()
        session.query(NewsSignalResult).delete()
        session.query(PriceSnapshot).delete()
        session.query(NewsItem).delete()
        session.commit()


def _add_news(
    session,
    *,
    key: str,
    sentiment: str,
    published_at: datetime,
    market: str = "us",
) -> NewsItem:
    news = NewsItem(
        source_name="unit-src",
        source_url="https://example.test/source",
        title=f"news-{key}",
        summary=None,
        canonical_url=f"https://example.test/{key}",
        url_hash=f"hash-{key}",
        market=market,
        sentiment_label=sentiment,
        sentiment_score=0.5 if sentiment == "positive" else -0.5,
        published_at=published_at,
        fetched_at=published_at,
    )
    session.add(news)
    session.flush()
    return news


def _add_signal(session, *, news_id: int, confidence: float | None) -> None:
    session.add(
        NewsSignalResult(
            news_id=news_id,
            classifier_type="rule",
            signal_confidence=confidence,
            topic_key=f"topic-{news_id}",
        )
    )


def _add_mention(session, *, news_id: int, symbol: str, market: str = "us") -> None:
    session.add(
        NewsStockMention(
            news_id=news_id,
            symbol=symbol,
            market=market,
            mention_type="body",
            confidence=0.9,
        )
    )


def _add_snapshot(session, *, symbol: str, price: float, fetched_at: datetime, market: str = "us") -> None:
    session.add(
        PriceSnapshot(
            symbol=symbol,
            market=market,
            price=price,
            fetched_at=fetched_at,
        )
    )


def test_backtest_hit_rate_returns_and_importance_buckets() -> None:
    """核心场景：命中率、平均前视收益、分桶收益与样本计数正确。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        # A: 利好 + 上涨 -> 命中，confidence 高
        a = _add_news(session, key="A", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=a.id, confidence=0.8)
        _add_mention(session, news_id=a.id, symbol="AAA")
        _add_snapshot(session, symbol="AAA", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="AAA", price=110.0, fetched_at=t0 + hour)

        # F: 利好 + 下跌 -> 未命中，confidence 高
        f = _add_news(session, key="F", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=f.id, confidence=0.7)
        _add_mention(session, news_id=f.id, symbol="FFF")
        _add_snapshot(session, symbol="FFF", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="FFF", price=95.0, fetched_at=t0 + hour)

        # B: 利空 + 下跌 -> 命中，confidence 中
        b = _add_news(session, key="B", sentiment="negative", published_at=t0)
        _add_signal(session, news_id=b.id, confidence=0.5)
        _add_mention(session, news_id=b.id, symbol="BBB")
        _add_snapshot(session, symbol="BBB", price=200.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="BBB", price=190.0, fetched_at=t0 + hour)

        # C: 利好但前视窗内无更晚快照 -> 跳过（稀疏降级）
        c = _add_news(session, key="C", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=c.id, confidence=0.9)
        _add_mention(session, news_id=c.id, symbol="CCC")
        _add_snapshot(session, symbol="CCC", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="CCC", price=105.0, fetched_at=t0 + timedelta(minutes=30))

        session.commit()

        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    assert result["total_signals"] == 4
    assert result["evaluable_count"] == 3
    assert result["skipped_count"] == 1
    assert result["evaluable_rate"] == pytest.approx(0.75)

    positive = result["positive"]
    assert positive["sample_count"] == 2
    assert positive["hit_count"] == 1
    assert positive["hit_rate"] == pytest.approx(0.5)
    assert positive["avg_forward_return"] == pytest.approx(0.025)

    negative = result["negative"]
    assert negative["sample_count"] == 1
    assert negative["hit_count"] == 1
    assert negative["hit_rate"] == pytest.approx(1.0)
    assert negative["avg_forward_return"] == pytest.approx(-0.05)

    buckets = {item["bucket"]: item for item in result["importance_buckets"]}
    assert buckets["high"]["sample_count"] == 2
    assert buckets["high"]["avg_forward_return"] == pytest.approx(0.025)
    assert buckets["medium"]["sample_count"] == 1
    assert buckets["medium"]["avg_forward_return"] == pytest.approx(-0.05)


def test_backtest_skips_when_baseline_snapshot_missing() -> None:
    """基准价缺失（发布前无快照）时优雅跳过并计入 skipped。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        e = _add_news(session, key="E", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=e.id, confidence=0.8)
        _add_mention(session, news_id=e.id, symbol="EEE")
        # 仅有发布之后的快照，没有基准价
        _add_snapshot(session, symbol="EEE", price=100.0, fetched_at=t0 + hour)
        _add_snapshot(session, symbol="EEE", price=110.0, fetched_at=t0 + 2 * hour)
        session.commit()

        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    assert result["total_signals"] == 1
    assert result["evaluable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["evaluable_rate"] == pytest.approx(0.0)
    assert result["positive"]["sample_count"] == 0
    assert result["positive"]["hit_rate"] is None
    assert result["positive"]["avg_forward_return"] is None


def test_backtest_excludes_news_outside_window() -> None:
    """回看窗口外的历史新闻被排除，不进入候选样本。"""
    _clean()
    now = datetime.now(UTC)
    old = now - timedelta(days=60)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        d = _add_news(session, key="D", sentiment="positive", published_at=old)
        _add_signal(session, news_id=d.id, confidence=0.8)
        _add_mention(session, news_id=d.id, symbol="DDD")
        _add_snapshot(session, symbol="DDD", price=100.0, fetched_at=old - hour)
        _add_snapshot(session, symbol="DDD", price=120.0, fetched_at=old + hour)
        session.commit()

        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    assert result["total_signals"] == 0
    assert result["evaluable_count"] == 0
    assert result["skipped_count"] == 0
    assert result["evaluable_rate"] is None


def test_backtest_market_filter_narrows_candidates() -> None:
    """market 过滤仅统计对应市场的新闻信号。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        us = _add_news(session, key="US", sentiment="positive", published_at=t0, market="us")
        _add_signal(session, news_id=us.id, confidence=0.8)
        _add_mention(session, news_id=us.id, symbol="USX", market="us")
        _add_snapshot(session, symbol="USX", price=100.0, fetched_at=t0 - hour, market="us")
        _add_snapshot(session, symbol="USX", price=110.0, fetched_at=t0 + hour, market="us")
        session.commit()

        hk_result = SignalBacktestService(session).run(market="hk", window_days=30, horizon="1h", now=now)
        us_result = SignalBacktestService(session).run(market="us", window_days=30, horizon="1h", now=now)

    assert hk_result["total_signals"] == 0
    assert us_result["total_signals"] == 1
    assert us_result["evaluable_count"] == 1
    assert us_result["market"] == "us"


def test_backtest_route_returns_summary() -> None:
    """路由冒烟：GET /api/backtest 返回 200 与预期字段。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        a = _add_news(session, key="RT", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=a.id, confidence=0.8)
        _add_mention(session, news_id=a.id, symbol="RTX")
        _add_snapshot(session, symbol="RTX", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="RTX", price=110.0, fetched_at=t0 + hour)
        session.commit()

    client = TestClient(app)
    response = client.get("/api/backtest", params={"window_days": 30, "horizon": "1h"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["horizon"] == "1h"
    assert payload["window_days"] == 30
    assert payload["total_signals"] == 1
    assert payload["positive"]["sample_count"] == 1
    assert "importance_buckets" in payload
    assert "generated_at" in payload


def test_backtest_route_rejects_invalid_horizon() -> None:
    """非法 horizon 返回 400。"""
    _clean()
    client = TestClient(app)
    response = client.get("/api/backtest", params={"horizon": "abc"})
    assert response.status_code == 400
