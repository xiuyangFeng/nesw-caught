"""市场总览 - 新闻情绪按市场聚合服务测试(B5)。

覆盖设计文档"六、新闻情绪按市场聚合方案":
- 三级归属: mention 市场集中度 >= 60% 优先 -> news_item.market 兜底 -> 不归属
- hk 并入 cn; 未映射市场不归属任何目标市场
- 滚动 24h 窗口; 单条分数 sentiment_score 优先, 缺则回退 analysis sentiment 标签映射
- 样本 < 3 返回 insufficient_data
- top_signals 按 signal_confidence 降序取前 5
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.news_analysis_result import NewsAnalysisResult
from app.models.news_item import NewsItem
from app.models.news_signal_result import NewsSignalResult
from app.models.news_stock_mention import NewsStockMention
from app.services.market_sentiment_service import (
    aggregate_all_markets,
    aggregate_news_sentiment,
)

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
_url_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def _clean_news_tables():
    with SessionLocal() as session:
        session.query(NewsSignalResult).delete()
        session.query(NewsAnalysisResult).delete()
        session.query(NewsStockMention).delete()
        session.query(NewsItem).delete()
        session.commit()
    yield


def _make_news(
    session: Session,
    *,
    market: str,
    title: str = "news",
    sentiment_score: float | None = 0.5,
    published_at: datetime | None = None,
    source_name: str = "unit-source",
) -> NewsItem:
    n = next(_url_counter)
    item = NewsItem(
        source_name=source_name,
        source_url=f"https://src.example.com/{n}",
        title=title,
        summary=f"summary {n}",
        canonical_url=f"https://src.example.com/news/{n}",
        url_hash=f"hash-{n}",
        market=market,
        sentiment_score=sentiment_score,
        published_at=published_at or NOW,
        fetched_at=published_at or NOW,
    )
    session.add(item)
    session.flush()
    return item


def _add_mentions(session: Session, news_id: int, markets: list[str]) -> None:
    for idx, market in enumerate(markets):
        session.add(
            NewsStockMention(
                news_id=news_id,
                symbol=f"SYM{idx}",
                market=market,
                mention_type="body",
                confidence=0.9,
            )
        )


def _add_analysis(session: Session, news_id: int, sentiment: str) -> None:
    session.add(
        NewsAnalysisResult(
            news_id=news_id,
            provider_name="unit-llm",
            model_name="unit-model",
            sentiment=sentiment,
        )
    )


def _add_signal(session: Session, news_id: int, confidence: float | None) -> None:
    session.add(
        NewsSignalResult(
            news_id=news_id,
            classifier_type="rule",
            signal_confidence=confidence,
        )
    )


# ---------------------------------------------------------------------------
# 归属映射
# ---------------------------------------------------------------------------


def test_mention_concentration_overrides_news_market() -> None:
    """mention 集中度 >= 60% 时归属 mention 市场, 覆盖 news_item.market。"""
    with SessionLocal() as session:
        # news_item.market=us, 但 3 条 mention 中 2 条 cn(66.7%) -> 归属 cn
        concentrated = _make_news(session, market="us", sentiment_score=0.6)
        _add_mentions(session, concentrated.id, ["cn", "cn", "us"])
        # 补足 cn 样本到 3 条
        _make_news(session, market="cn", sentiment_score=0.2)
        _make_news(session, market="cn", sentiment_score=0.4)
        session.commit()

        cn_result = aggregate_news_sentiment(session, "cn", now=NOW)
        us_result = aggregate_news_sentiment(session, "us", now=NOW)

    assert cn_result.status == "ok"
    assert cn_result.sample_count == 3
    assert cn_result.score == pytest.approx((0.6 + 0.2 + 0.4) / 3)
    # us 市场没有归属任何新闻
    assert us_result.status == "insufficient_data"
    assert us_result.sample_count == 0
    assert us_result.score is None


def test_mention_exact_threshold_60_percent_concentrated() -> None:
    """5 条 mention 中 3 条同市场 = 恰好 60%, 仍视为集中。"""
    with SessionLocal() as session:
        item = _make_news(session, market="us", sentiment_score=0.9)
        _add_mentions(session, item.id, ["jp", "jp", "jp", "us", "cn"])
        session.commit()

        jp_result = aggregate_news_sentiment(session, "jp", now=NOW)
        us_result = aggregate_news_sentiment(session, "us", now=NOW)

    # 归属 jp 但样本只有 1 条, 分数按 insufficient_data 规则为 None
    assert jp_result.sample_count == 1
    assert jp_result.status == "insufficient_data"
    assert jp_result.score is None
    assert us_result.sample_count == 0


def test_dispersed_mentions_fall_back_to_news_market() -> None:
    """mention 分散(各 1/3)时回退 news_item.market; hk 并入 cn。"""
    with SessionLocal() as session:
        item = _make_news(session, market="hk", sentiment_score=-0.4)
        _add_mentions(session, item.id, ["us", "kr", "jp"])
        session.commit()

        cn_result = aggregate_news_sentiment(session, "cn", now=NOW)
        us_result = aggregate_news_sentiment(session, "us", now=NOW)

    assert cn_result.sample_count == 1
    # 样本不足 3 条, 分数为 None, 但归属正确(cn 计入了该新闻)
    assert cn_result.status == "insufficient_data"
    assert cn_result.score is None
    assert us_result.sample_count == 0


def test_no_mentions_uses_news_item_market() -> None:
    with SessionLocal() as session:
        _make_news(session, market="us", sentiment_score=0.3)
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.sample_count == 1
    assert result.status == "insufficient_data"


def test_hk_news_merged_into_cn() -> None:
    with SessionLocal() as session:
        _make_news(session, market="hk", sentiment_score=0.1)
        _make_news(session, market="cn", sentiment_score=0.3)
        _make_news(session, market="cn", sentiment_score=0.5)
        session.commit()

        result = aggregate_news_sentiment(session, "cn", now=NOW)

    assert result.status == "ok"
    assert result.sample_count == 3
    assert result.score == pytest.approx(0.3)


def test_unmapped_market_not_attributed() -> None:
    """news_item.market 不在映射表(如 fr)时, 新闻不归属任何目标市场。"""
    with SessionLocal() as session:
        _make_news(session, market="fr", sentiment_score=1.0)
        session.commit()

        results = aggregate_all_markets(session, now=NOW)

    assert set(results.keys()) == {"us", "cn", "kr", "jp", "eu"}
    for result in results.values():
        assert result.sample_count == 0
        assert result.status == "insufficient_data"


def test_unknown_market_argument_rejected() -> None:
    with SessionLocal() as session:
        with pytest.raises(ValueError):
            aggregate_news_sentiment(session, "hk", now=NOW)


# ---------------------------------------------------------------------------
# 分数计算
# ---------------------------------------------------------------------------


def test_sentiment_score_preferred_over_analysis_label() -> None:
    with SessionLocal() as session:
        # 三条新闻均有 sentiment_score, analysis 标签相反; 平均分应来自 score
        for score, label in [(0.5, "negative"), (0.7, "negative"), (0.3, "positive")]:
            item = _make_news(session, market="us", sentiment_score=score)
            _add_analysis(session, item.id, label)
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.status == "ok"
    assert result.score == pytest.approx(0.5)


def test_fallback_to_analysis_sentiment_label_mapping() -> None:
    """sentiment_score 缺失时回退 positive->+1 / neutral->0 / negative->-1。"""
    with SessionLocal() as session:
        pos = _make_news(session, market="us", sentiment_score=None)
        _add_analysis(session, pos.id, "positive")
        neu = _make_news(session, market="us", sentiment_score=None)
        _add_analysis(session, neu.id, "neutral")
        neg = _make_news(session, market="us", sentiment_score=None)
        _add_analysis(session, neg.id, "negative")
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.status == "ok"
    assert result.sample_count == 3
    assert result.score == pytest.approx(0.0)


def test_news_without_any_score_excluded_from_sample() -> None:
    """既无 sentiment_score 也无 analysis 标签的新闻不计入样本。"""
    with SessionLocal() as session:
        _make_news(session, market="us", sentiment_score=0.6)
        _make_news(session, market="us", sentiment_score=0.6)
        _make_news(session, market="us", sentiment_score=None)  # 无任何分数
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.sample_count == 2
    assert result.status == "insufficient_data"
    assert result.score is None


def test_insufficient_data_below_min_sample() -> None:
    with SessionLocal() as session:
        _make_news(session, market="kr", sentiment_score=0.8)
        _make_news(session, market="kr", sentiment_score=0.8)
        session.commit()

        result = aggregate_news_sentiment(session, "kr", now=NOW)

    assert result.status == "insufficient_data"
    assert result.score is None
    assert result.sample_count == 2
    assert result.top_signals == []


def test_rolling_window_excludes_old_news() -> None:
    """滚动 24h 窗口: 窗口外的新闻不参与聚合。"""
    with SessionLocal() as session:
        _make_news(session, market="us", sentiment_score=1.0,
                   published_at=NOW - timedelta(hours=25))
        _make_news(session, market="us", sentiment_score=1.0,
                   published_at=NOW - timedelta(hours=30))
        for score in (0.2, 0.4, 0.6):
            _make_news(session, market="us", sentiment_score=score,
                       published_at=NOW - timedelta(hours=1))
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.sample_count == 3
    assert result.score == pytest.approx(0.4)


def test_custom_lookback_hours() -> None:
    with SessionLocal() as session:
        _make_news(session, market="us", sentiment_score=0.7,
                   published_at=NOW - timedelta(hours=10))
        session.commit()

        narrow = aggregate_news_sentiment(session, "us", now=NOW, lookback_hours=6)
        wide = aggregate_news_sentiment(session, "us", now=NOW, lookback_hours=12)

    assert narrow.sample_count == 0
    assert wide.sample_count == 1


# ---------------------------------------------------------------------------
# top_signals
# ---------------------------------------------------------------------------


def test_top_signals_sorted_by_confidence_and_truncated() -> None:
    with SessionLocal() as session:
        items = []
        for idx, confidence in enumerate([0.1, 0.9, 0.5, 0.7, 0.3, 0.8, 0.2]):
            item = _make_news(
                session,
                market="us",
                title=f"signal news {idx}",
                sentiment_score=0.0,
            )
            _add_signal(session, item.id, confidence)
            items.append(item)
        session.commit()
        expected_ids = [items[i].id for i in [1, 5, 3, 2, 4]]

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert [s.news_id for s in result.top_signals] == expected_ids
    first = result.top_signals[0]
    assert first.title == "signal news 1"
    assert first.summary is not None
    assert first.signal_confidence == pytest.approx(0.9)
    assert first.source_name == "unit-source"
    assert first.published_at is not None
    assert first.canonical_url.startswith("https://src.example.com/news/")


def test_top_signals_only_from_own_market() -> None:
    with SessionLocal() as session:
        us_item = _make_news(session, market="us", sentiment_score=0.0)
        _add_signal(session, us_item.id, 0.9)
        cn_item = _make_news(session, market="cn", sentiment_score=0.0)
        _add_signal(session, cn_item.id, 0.99)
        us_id = us_item.id
        session.commit()

        us_result = aggregate_news_sentiment(session, "us", now=NOW)
        kr_result = aggregate_news_sentiment(session, "kr", now=NOW)

    assert [s.news_id for s in us_result.top_signals] == [us_id]
    assert kr_result.top_signals == []


def test_top_signals_present_even_when_insufficient_data() -> None:
    """样本不足时 score 为 null, 但窗口内的信号列表仍正常返回。"""
    with SessionLocal() as session:
        item = _make_news(session, market="us", sentiment_score=0.0)
        _add_signal(session, item.id, 0.8)
        news_id = item.id
        session.commit()

        result = aggregate_news_sentiment(session, "us", now=NOW)

    assert result.status == "insufficient_data"
    assert result.score is None
    assert [s.news_id for s in result.top_signals] == [news_id]


def test_aggregate_all_markets_returns_five_skeletons() -> None:
    with SessionLocal() as session:
        _make_news(session, market="us", sentiment_score=0.2)
        session.commit()

        results = aggregate_all_markets(session, now=NOW)

    assert set(results.keys()) == {"us", "cn", "kr", "jp", "eu"}
    assert results["us"].sample_count == 1
    for market in ("cn", "kr", "jp", "eu"):
        assert results[market].status == "insufficient_data"
        assert results[market].score is None
        assert results[market].sample_count == 0
        assert results[market].top_signals == []



# ---------------------------------------------------------------------------
# 量化情绪纯函数 compute_market_sentiment（计划任务 B3，设计文档七节）
#
# 规则：指数动量权重 0.6 / VIX 权重 0.25（仅可得时）/ 涨跌家数权重 0.15（仅可得时）；
# 缺输入按剩余输入重新归一权重，全缺返回 label="unknown"。
# 分段锚点（区间内线性插值，段外钳制）：
# - 指数动量 avg_chg：(-2 -> -1) (-0.5 -> -0.5) (+0.5 -> 0) (+2 -> +0.5)，>= +2 -> +1
# - VIX：13 -> +0.5 / 20 -> 0 / 30 -> -0.5，<13 -> +0.5，>=30 -> -1
# - 涨跌家数 adv_ratio：(0.3 -> -0.5) (0.7 -> +0.5)，<=0.3 -> -0.5，>=0.7 -> +0.5
# 标签阈值：score <= -0.6 panic；<= -0.2 fear；<= +0.2 neutral；<= +0.6 greed；> +0.6 greed_extreme
# ---------------------------------------------------------------------------

from app.services.market_sentiment_service import (  # noqa: E402
    BoardStats,
    SentimentIndexQuote,
    compute_market_sentiment,
)


def _indices(*change_percents: float | None) -> list[SentimentIndexQuote]:
    return [SentimentIndexQuote(change_percent=cp) for cp in change_percents]


def test_quant_momentum_segment_interpolation() -> None:
    # avg_chg = 1.25 落在 [0.5, 2] -> [0, 0.5]：0.75/1.5 * 0.5 = 0.25
    result = compute_market_sentiment(_indices(1.0, 1.5), vix=None, board_stats=None)

    assert result.score == pytest.approx(0.25)
    assert result.label == "greed"
    assert result.inputs["avg_change_percent"] == pytest.approx(1.25)
    assert result.inputs["vix"] is None
    assert result.inputs["adv_ratio"] is None


def test_quant_momentum_negative_segment() -> None:
    # avg_chg = -1.25 落在 [-2, -0.5] -> [-1, -0.5]：-1 + 0.75/1.5 * 0.5 = -0.75
    result = compute_market_sentiment(_indices(-1.25), vix=None, board_stats=None)

    assert result.score == pytest.approx(-0.75)
    assert result.label == "panic"


def test_quant_momentum_extreme_clamps() -> None:
    up = compute_market_sentiment(_indices(3.5), vix=None, board_stats=None)
    down = compute_market_sentiment(_indices(-3.5), vix=None, board_stats=None)

    assert up.score == pytest.approx(1.0)
    assert up.label == "greed_extreme"
    assert down.score == pytest.approx(-1.0)
    assert down.label == "panic"


def test_quant_momentum_neutral_zone() -> None:
    # avg_chg = 0.25 落在 [-0.5, 0.5] -> [-0.5, 0]：-0.5 + 0.75*0.5 = -0.125 -> neutral
    result = compute_market_sentiment(_indices(0.3, 0.2), vix=None, board_stats=None)

    assert result.score == pytest.approx(-0.125)
    assert result.label == "neutral"


def test_quant_indices_with_none_change_percent_excluded() -> None:
    result = compute_market_sentiment(_indices(None, 2.5), vix=None, board_stats=None)

    assert result.inputs["avg_change_percent"] == pytest.approx(2.5)
    assert result.score == pytest.approx(1.0)


def test_quant_vix_segments() -> None:
    # 只有 VIX 可得时权重归一到 VIX 本身，score 即 VIX 分项。
    low = compute_market_sentiment([], vix=12.0, board_stats=None)
    mid = compute_market_sentiment([], vix=16.5, board_stats=None)
    high = compute_market_sentiment([], vix=25.0, board_stats=None)
    extreme = compute_market_sentiment([], vix=35.0, board_stats=None)

    assert low.score == pytest.approx(0.5)  # <13 低波贪婪
    assert mid.score == pytest.approx(0.25)  # [13,20] -> [+0.5, 0]
    assert high.score == pytest.approx(-0.25)  # [20,30] -> [0, -0.5]
    assert extreme.score == pytest.approx(-1.0)  # >=30 恐慌
    assert extreme.label == "panic"


def test_quant_weights_combine_momentum_and_vix() -> None:
    # 动量 avg=0 -> -0.25 分（[-0.5,0.5] 段插值，权重 0.6），VIX=35 -> -1 分（权重 0.25）
    # score = (-0.25*0.6 + -1*0.25) / 0.85
    result = compute_market_sentiment(_indices(0.0), vix=35.0, board_stats=None)

    assert result.score == pytest.approx(-0.4 / 0.85)
    assert result.label == "fear"
    assert result.inputs["vix"] == pytest.approx(35.0)


def test_quant_missing_vix_yields_weight_to_momentum() -> None:
    # VIX 缺失时 0.25 权重让渡：score = 动量分项本身。
    # avg=1.5 落在 [0.5,2] -> (1.0/1.5)*0.5 ≈ 0.333 -> greed
    result = compute_market_sentiment(_indices(1.5), vix=None, board_stats=None)

    assert result.score == pytest.approx(1.0 / 3.0)
    assert result.label == "greed"


def test_quant_board_stats_advance_ratio() -> None:
    # adv_ratio = 80/(80+20+0) = 0.8 >= 0.7 -> +0.5（权重 0.15）
    # 动量 avg=0 -> -0.25 分（权重 0.6）：score = (-0.25*0.6 + 0.5*0.15)/0.75 = -0.1
    board = BoardStats(advance_count=80, decline_count=20, flat_count=0)
    result = compute_market_sentiment(_indices(0.0), vix=None, board_stats=board)

    assert result.inputs["adv_ratio"] == pytest.approx(0.8)
    assert result.score == pytest.approx(-0.1)
    assert result.label == "neutral"


def test_quant_board_stats_low_advance_ratio() -> None:
    # adv_ratio = 0.2 <= 0.3 -> -0.5；只有板块可得时 score = -0.5
    board = BoardStats(advance_count=20, decline_count=70, flat_count=10)
    result = compute_market_sentiment([], vix=None, board_stats=board)

    assert result.inputs["adv_ratio"] == pytest.approx(0.2)
    assert result.score == pytest.approx(-0.5)
    assert result.label == "fear"


def test_quant_board_stats_zero_counts_treated_missing() -> None:
    board = BoardStats(advance_count=0, decline_count=0, flat_count=0)
    result = compute_market_sentiment([], vix=None, board_stats=board)

    assert result.inputs["adv_ratio"] is None
    assert result.label == "unknown"
    assert result.score is None


def test_quant_all_inputs_missing_returns_unknown() -> None:
    result = compute_market_sentiment([], vix=None, board_stats=None)

    assert result.score is None
    assert result.label == "unknown"
    assert result.inputs["avg_change_percent"] is None


def test_quant_label_thresholds() -> None:
    # 通过板块 adv_ratio 线性段精确构造 score 边界值：
    # 只有板块可得时 score 分项 = lerp(0.3->-0.5, 0.7->+0.5)
    def score_for_ratio(adv: int, dec: int) -> float:
        board = BoardStats(advance_count=adv, decline_count=dec, flat_count=0)
        return compute_market_sentiment([], vix=None, board_stats=board).score

    # adv_ratio=0.55 -> score=0.125 -> neutral 上界内；直接验证标签阈值用动量更精确。
    assert compute_market_sentiment(_indices(-2.0), vix=None, board_stats=None).label == "panic"  # score=-1
    # score 恰为 -0.6：动量 avg=-1.4 -> -1 + (0.6/1.5)*0.5 = -0.8... 用组合构造：
    # 动量 avg=-2 -> -1（0.6），VIX=20 -> 0（0.25）：score = -0.6/0.85 ≈ -0.706 -> panic
    assert compute_market_sentiment(_indices(-2.0), vix=20.0, board_stats=None).label == "panic"
    # 动量 avg=2 -> 钳制 +1（0.6），VIX=20 -> 0（0.25）：score = 0.6/0.85 ≈ 0.706 -> greed_extreme
    assert compute_market_sentiment(_indices(2.0), vix=20.0, board_stats=None).label == "greed_extreme"
    # 段内 neutral：动量 avg=1.0 -> (0.5/1.5)*0.5 ≈ 0.167 -> neutral
    assert compute_market_sentiment(_indices(1.0), vix=None, board_stats=None).label == "neutral"
    assert score_for_ratio(55, 45) == pytest.approx(0.125)
