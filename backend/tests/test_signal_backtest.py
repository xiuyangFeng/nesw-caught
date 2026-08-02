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
    score: float | None = None,
) -> NewsItem:
    default_score = 0.5 if sentiment == "positive" else -0.5
    news = NewsItem(
        source_name="unit-src",
        source_url="https://example.test/source",
        title=f"news-{key}",
        summary=None,
        canonical_url=f"https://example.test/{key}",
        url_hash=f"hash-{key}",
        market=market,
        sentiment_label=sentiment,
        sentiment_score=default_score if score is None else score,
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


# —— Phase 2 / 工作块 E：超额收益、陈旧过滤、样本相关性、score 分桶 ——


def test_backtest_excess_return_uses_proxy_benchmark() -> None:
    """无真实指数基准时，excess_return 用同窗口全部可评样本的平均前视收益做代理基准。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        # G: +10%
        g = _add_news(session, key="G", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=g.id, confidence=0.8)
        _add_mention(session, news_id=g.id, symbol="GGG")
        _add_snapshot(session, symbol="GGG", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="GGG", price=110.0, fetched_at=t0 + hour)

        # H: -10%
        h = _add_news(session, key="H", sentiment="negative", published_at=t0)
        _add_signal(session, news_id=h.id, confidence=0.8)
        _add_mention(session, news_id=h.id, symbol="HHH")
        _add_snapshot(session, symbol="HHH", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="HHH", price=90.0, fetched_at=t0 + hour)

        session.commit()
        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    # 代理基准 = 平均前视收益 = (0.10 + (-0.10)) / 2 = 0.0
    assert result["benchmark_return"] == pytest.approx(0.0)
    assert "代理" in result["benchmark_note"] or "proxy" in result["benchmark_note"].lower()
    assert result["avg_excess_return"] == pytest.approx(0.0)
    # positive 样本超额收益 = 0.10 - 0.0 = 0.10；negative 样本超额收益 = -0.10 - 0.0 = -0.10
    assert result["positive"]["avg_excess_return"] == pytest.approx(0.10)
    assert result["negative"]["avg_excess_return"] == pytest.approx(-0.10)


def test_backtest_skips_stale_baseline_snapshot() -> None:
    """baseline 快照距发布时间超过 signal_backtest_max_snapshot_age_hours（默认 24h）时跳过并计数。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        i = _add_news(session, key="I", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=i.id, confidence=0.8)
        _add_mention(session, news_id=i.id, symbol="III")
        # 唯一的 baseline 候选快照是发布前 30 小时的，超过默认 24h 陈旧门槛
        _add_snapshot(session, symbol="III", price=100.0, fetched_at=t0 - 30 * hour)
        _add_snapshot(session, symbol="III", price=110.0, fetched_at=t0 + hour)
        session.commit()

        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    assert result["total_signals"] == 1
    assert result["evaluable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_stale_count"] == 1


def test_backtest_per_news_hit_rate_differs_from_sample_hit_rate() -> None:
    """一条新闻多只股票产生多个样本，per_news_hit_rate 与逐样本 hit_rate 应有区别。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        # 新闻 J：利好，提及 1 只股票，命中（上涨）
        j = _add_news(session, key="J", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=j.id, confidence=0.8)
        _add_mention(session, news_id=j.id, symbol="JJJ")
        _add_snapshot(session, symbol="JJJ", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="JJJ", price=110.0, fetched_at=t0 + hour)

        # 新闻 K：利好，提及 2 只股票，1 命中（上涨）+ 1 未命中（下跌）
        k = _add_news(session, key="K", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=k.id, confidence=0.8)
        _add_mention(session, news_id=k.id, symbol="KKK1")
        _add_mention(session, news_id=k.id, symbol="KKK2")
        _add_snapshot(session, symbol="KKK1", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="KKK1", price=110.0, fetched_at=t0 + hour)
        _add_snapshot(session, symbol="KKK2", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="KKK2", price=90.0, fetched_at=t0 + hour)

        session.commit()
        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    # 逐样本命中率（news x symbol 展开）：3 个样本，2 命中 -> 0.6667
    assert result["positive"]["sample_count"] == 3
    assert result["positive"]["hit_rate"] == pytest.approx(2 / 3, abs=1e-4)
    # per-news：新闻 J 内部命中均值 1.0；新闻 K 内部命中均值 0.5 -> 两条新闻等权均值 0.75
    assert result["distinct_news_count"] == 2
    assert result["per_news_hit_rate"] == pytest.approx(0.75)


def test_backtest_score_buckets_group_by_abs_sentiment_score() -> None:
    """score_buckets 按 |sentiment_score| 落桶，命中率/收益按桶聚合。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        # 低分（0.1，命中）落在 0.0-0.2 桶
        low = _add_news(session, key="LOW", sentiment="positive", published_at=t0, score=0.1)
        _add_signal(session, news_id=low.id, confidence=0.4)
        _add_mention(session, news_id=low.id, symbol="LOWS")
        _add_snapshot(session, symbol="LOWS", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="LOWS", price=105.0, fetched_at=t0 + hour)

        # 高分（0.9，命中）落在 0.8-1.0 桶
        high = _add_news(session, key="HIGH", sentiment="positive", published_at=t0, score=0.9)
        _add_signal(session, news_id=high.id, confidence=0.9)
        _add_mention(session, news_id=high.id, symbol="HIGHS")
        _add_snapshot(session, symbol="HIGHS", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="HIGHS", price=120.0, fetched_at=t0 + hour)

        session.commit()
        result = SignalBacktestService(session).run(window_days=30, horizon="1h", now=now)

    buckets = {item["range_label"]: item for item in result["score_buckets"]}
    assert set(buckets) == {"0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"}
    assert buckets["0.0-0.2"]["sample_count"] == 1
    assert buckets["0.0-0.2"]["hit_rate"] == pytest.approx(1.0)
    assert buckets["0.8-1.0"]["sample_count"] == 1
    assert buckets["0.8-1.0"]["hit_rate"] == pytest.approx(1.0)
    assert buckets["0.2-0.4"]["sample_count"] == 0
    assert buckets["0.2-0.4"]["hit_rate"] is None


def test_backtest_route_response_includes_phase2_fields() -> None:
    """路由响应带上 Phase 2 新字段（含顺带落盘的 calibration）。"""
    _clean()
    now = datetime.now(UTC)
    t0 = now - timedelta(days=1)
    hour = timedelta(hours=1)

    with SessionLocal() as session:
        news = _add_news(session, key="RT2", sentiment="positive", published_at=t0)
        _add_signal(session, news_id=news.id, confidence=0.8)
        _add_mention(session, news_id=news.id, symbol="RTX2")
        _add_snapshot(session, symbol="RTX2", price=100.0, fetched_at=t0 - hour)
        _add_snapshot(session, symbol="RTX2", price=110.0, fetched_at=t0 + hour)
        session.commit()

    client = TestClient(app)
    response = client.get("/api/backtest", params={"window_days": 30, "horizon": "1h"})

    assert response.status_code == 200
    payload = response.json()
    for field in (
        "avg_excess_return",
        "benchmark_note",
        "benchmark_return",
        "distinct_news_count",
        "per_news_hit_rate",
        "skipped_stale_count",
        "score_buckets",
        "calibration",
    ):
        assert field in payload
    assert payload["calibration"] is not None
    assert "mapping" in payload["calibration"]
