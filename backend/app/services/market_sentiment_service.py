"""市场总览 - 新闻情绪按市场聚合服务(B5)。

设计契约: docs/superpowers/specs/2026-08-02-market-overview-design.md 第六节。

- 归属映射三级优先级: news_stock_mention 市场集中度 >= 60% -> news_item.market 兜底 -> 不归属
- hk 并入 cn; 未映射市场(如 fr)的新闻不进入任何目标市场
- 滚动窗口(默认 24h, 不按自然日/时区切割), 以 news_item.effective_at 过滤
- 单条分数: news_item.sentiment_score 优先, 缺则回退 news_analysis_result.sentiment
  标签映射(positive->+1 / neutral->0 / negative->-1); 两者皆无的新闻不计入样本
- 样本数 < MIN_SAMPLE_COUNT 时 status="insufficient_data", score=None
- top_signals: 该市场窗口内 news_signal_result join news_item, 按 signal_confidence
  降序取前 TOP_SIGNALS_LIMIT 条(样本不足时仍返回信号列表)

常量按并行开发约定定义在本模块级(core/config.py 由其他任务独占), 后续 B2 的配置项
market_overview_news_lookback_hours 落地后可由调用方通过 lookback_hours 参数传入。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_analysis_result import NewsAnalysisResult
from app.models.news_item import NewsItem
from app.models.news_signal_result import NewsSignalResult
from app.models.news_stock_mention import NewsStockMention

# 目标市场(固定五市场骨架, 顺序即展示顺序)。
TARGET_MARKETS: tuple[str, ...] = ("us", "cn", "kr", "jp", "eu")

# 原始市场值 -> 目标市场。hk 并入 cn; 不在表内的市场值不归属任何目标市场。
_NEWS_MARKET_MAP: dict[str, str] = {
    "us": "us",
    "cn": "cn",
    "hk": "cn",
    "kr": "kr",
    "jp": "jp",
    "eu": "eu",
}

# news_analysis_result.sentiment 标签 -> 分数的回退映射。
_SENTIMENT_LABEL_SCORES: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}

NEWS_LOOKBACK_HOURS: float = 24.0
MIN_SAMPLE_COUNT: int = 3
MENTION_CONCENTRATION_THRESHOLD: float = 0.6
TOP_SIGNALS_LIMIT: int = 5

STATUS_OK = "ok"
STATUS_INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class NewsSignalItem:
    """top_signals 列表项, 字段对齐 /api/market/overview 契约。"""

    news_id: int
    title: str
    summary: str | None
    signal_confidence: float | None
    source_name: str
    published_at: datetime | None
    canonical_url: str


@dataclass(frozen=True)
class MarketNewsSentiment:
    """单市场滚动窗口内的新闻情绪聚合结果。"""

    market: str
    status: str  # STATUS_OK | STATUS_INSUFFICIENT_DATA
    score: float | None
    sample_count: int
    top_signals: list[NewsSignalItem] = field(default_factory=list)


@dataclass(frozen=True)
class _NewsRow:
    """窗口内一条新闻参与聚合所需的最小字段集。"""

    id: int
    market: str
    sentiment_score: float | None
    title: str
    summary: str | None
    source_name: str
    published_at: datetime | None
    canonical_url: str


def _attribute_market(news_market: str, mention_markets: list[str]) -> str | None:
    """三级归属: mention 集中度优先, news_item.market 兜底, 否则不归属。"""
    mapped_mentions = [
        _NEWS_MARKET_MAP[m] for m in mention_markets if m in _NEWS_MARKET_MAP
    ]
    if mapped_mentions:
        top_market, top_count = Counter(mapped_mentions).most_common(1)[0]
        if top_count / len(mapped_mentions) >= MENTION_CONCENTRATION_THRESHOLD:
            return top_market
    return _NEWS_MARKET_MAP.get(news_market)


def _resolve_score(
    sentiment_score: float | None, analysis_sentiment: str | None
) -> float | None:
    """单条新闻分数: sentiment_score 优先, 缺则回退 analysis 标签映射。"""
    if sentiment_score is not None:
        return sentiment_score
    if analysis_sentiment is None:
        return None
    return _SENTIMENT_LABEL_SCORES.get(analysis_sentiment)


def _load_window_data(
    session: Session, window_start: datetime
) -> tuple[
    list[_NewsRow],
    dict[int, list[str]],
    dict[int, str | None],
    dict[int, float | None],
]:
    """一次取齐窗口内新闻及其 mention/analysis/signal 关联数据。"""
    news_rows = [
        _NewsRow(
            id=row.id,
            market=row.market,
            sentiment_score=row.sentiment_score,
            title=row.title,
            summary=row.summary,
            source_name=row.source_name,
            published_at=row.published_at,
            canonical_url=row.canonical_url,
        )
        for row in session.execute(
            select(
                NewsItem.id,
                NewsItem.market,
                NewsItem.sentiment_score,
                NewsItem.title,
                NewsItem.summary,
                NewsItem.source_name,
                NewsItem.published_at,
                NewsItem.canonical_url,
            ).where(NewsItem.effective_at >= window_start)
        )
    ]
    if not news_rows:
        return [], {}, {}, {}

    news_ids = [row.id for row in news_rows]

    mention_markets: dict[int, list[str]] = defaultdict(list)
    for news_id, market in session.execute(
        select(NewsStockMention.news_id, NewsStockMention.market).where(
            NewsStockMention.news_id.in_(news_ids)
        )
    ):
        mention_markets[news_id].append(market)

    analysis_sentiments: dict[int, str | None] = {}
    for news_id, sentiment in session.execute(
        select(NewsAnalysisResult.news_id, NewsAnalysisResult.sentiment).where(
            NewsAnalysisResult.news_id.in_(news_ids)
        )
    ):
        analysis_sentiments[news_id] = sentiment

    signal_confidences: dict[int, float | None] = {}
    for news_id, confidence in session.execute(
        select(NewsSignalResult.news_id, NewsSignalResult.signal_confidence).where(
            NewsSignalResult.news_id.in_(news_ids)
        )
    ):
        signal_confidences[news_id] = confidence

    return news_rows, mention_markets, analysis_sentiments, signal_confidences


def _aggregate_markets(
    session: Session,
    markets: tuple[str, ...],
    *,
    now: datetime | None,
    lookback_hours: float,
    top_signals_limit: int,
) -> dict[str, MarketNewsSentiment]:
    now = now or datetime.now(UTC)
    window_start = now - timedelta(hours=lookback_hours)
    news_rows, mention_markets, analysis_sentiments, signal_confidences = (
        _load_window_data(session, window_start)
    )

    # 归属: market -> 该市场窗口内的新闻列表。
    buckets: dict[str, list[_NewsRow]] = {market: [] for market in markets}
    for row in news_rows:
        target = _attribute_market(row.market, mention_markets.get(row.id, []))
        if target in buckets:
            buckets[target].append(row)

    results: dict[str, MarketNewsSentiment] = {}
    for market in markets:
        rows = buckets[market]

        scores = [
            score
            for row in rows
            if (
                score := _resolve_score(
                    row.sentiment_score, analysis_sentiments.get(row.id)
                )
            )
            is not None
        ]
        sample_count = len(scores)
        if sample_count >= MIN_SAMPLE_COUNT:
            status = STATUS_OK
            score: float | None = sum(scores) / sample_count
        else:
            status = STATUS_INSUFFICIENT_DATA
            score = None

        # top_signals: 归属本市场且有信号记录的新闻, confidence 降序(None 排最后)。
        signal_rows = [row for row in rows if row.id in signal_confidences]
        signal_rows.sort(
            key=lambda row: (
                signal_confidences[row.id] is not None,
                signal_confidences[row.id] or 0.0,
            ),
            reverse=True,
        )
        top_signals = [
            NewsSignalItem(
                news_id=row.id,
                title=row.title,
                summary=row.summary,
                signal_confidence=signal_confidences[row.id],
                source_name=row.source_name,
                published_at=row.published_at,
                canonical_url=row.canonical_url,
            )
            for row in signal_rows[:top_signals_limit]
        ]

        results[market] = MarketNewsSentiment(
            market=market,
            status=status,
            score=score,
            sample_count=sample_count,
            top_signals=top_signals,
        )
    return results


def aggregate_news_sentiment(
    session: Session,
    market: str,
    *,
    now: datetime | None = None,
    lookback_hours: float = NEWS_LOOKBACK_HOURS,
    top_signals_limit: int = TOP_SIGNALS_LIMIT,
) -> MarketNewsSentiment:
    """聚合单个目标市场滚动窗口内的新闻情绪。

    market 必须是 TARGET_MARKETS 之一(原始 hk 新闻通过映射并入 cn,
    不作为独立入参)。供 /api/market/overview 端点按市场调用。
    """
    if market not in TARGET_MARKETS:
        raise ValueError(f"unsupported market: {market!r}")
    return _aggregate_markets(
        session,
        (market,),
        now=now,
        lookback_hours=lookback_hours,
        top_signals_limit=top_signals_limit,
    )[market]


def aggregate_all_markets(
    session: Session,
    *,
    now: datetime | None = None,
    lookback_hours: float = NEWS_LOOKBACK_HOURS,
    top_signals_limit: int = TOP_SIGNALS_LIMIT,
) -> dict[str, MarketNewsSentiment]:
    """一次查询聚合全部五个目标市场(共享窗口数据, 避免逐市场重复扫描)。"""
    return _aggregate_markets(
        session,
        TARGET_MARKETS,
        now=now,
        lookback_hours=lookback_hours,
        top_signals_limit=top_signals_limit,
    )


# ---------------------------------------------------------------------------
# 量化情绪纯函数(B3)。设计契约: 同设计文档第七节。
#
# 权重: 指数动量 0.6 / VIX 0.25(仅可得时启用, 缺省让渡) / 涨跌家数 0.15(同上);
# 缺输入按剩余输入重新归一权重, 全缺返回 label="unknown", score=None。
# 分段规则按"区间右端点取值 + 区间内线性插值 + 段外钳制"实现:
# - 指数动量 avg_chg: [-2,-0.5]->[-1,-0.5]; [-0.5,+0.5]->[-0.5,0]; [+0.5,+2]->[0,+0.5];
#   avg<=-2 -> -1, avg>=+2 -> +1(设计文档原文 ">= +2 -> +1", 端点跳变与设计一致)
# - VIX: [13,20]->[+0.5,0]; [20,30]->[0,-0.5]; vix<13 -> +0.5, vix>=30 -> -1
# - 涨跌家数 adv_ratio: [0.3,0.7]->[-0.5,+0.5]; <=0.3 -> -0.5, >=0.7 -> +0.5
# 阈值常量按设计文档约定放模块级, 不进配置表。
# ---------------------------------------------------------------------------

WEIGHT_INDEX_MOMENTUM: float = 0.6
WEIGHT_VIX: float = 0.25
WEIGHT_ADVANCE_RATIO: float = 0.15

LABEL_PANIC = "panic"
LABEL_FEAR = "fear"
LABEL_NEUTRAL = "neutral"
LABEL_GREED = "greed"
LABEL_GREED_EXTREME = "greed_extreme"
LABEL_UNKNOWN = "unknown"


@dataclass(frozen=True)
class SentimentIndexQuote:
    """量化情绪输入: 单个指数的最新涨跌幅(%)。None 表示该指数数据缺失(不参与平均)。"""

    change_percent: float | None


@dataclass(frozen=True)
class BoardStats:
    """量化情绪输入: 全板块上涨/下跌/平盘家数合计(东财板块榜聚合)。"""

    advance_count: int
    decline_count: int
    flat_count: int


@dataclass(frozen=True)
class QuantSentiment:
    """单市场量化情绪结果。inputs 为参与计算的输入摘要(便于调试与前端展示)。"""

    score: float | None  # [-1, 1]; 全输入缺失时为 None
    label: str  # panic/fear/neutral/greed/greed_extreme/unknown
    inputs: dict[str, float | None]  # avg_change_percent / vix / adv_ratio


def _lerp(value: float, x0: float, y0: float, x1: float, y1: float) -> float:
    return y0 + (value - x0) * (y1 - y0) / (x1 - x0)


def _momentum_score(avg_change_percent: float) -> float:
    value = avg_change_percent
    if value <= -2.0:
        return -1.0
    if value >= 2.0:
        return 1.0
    if value < -0.5:
        return _lerp(value, -2.0, -1.0, -0.5, -0.5)
    if value <= 0.5:
        return _lerp(value, -0.5, -0.5, 0.5, 0.0)
    return _lerp(value, 0.5, 0.0, 2.0, 0.5)


def _vix_score(vix: float) -> float:
    if vix >= 30.0:
        return -1.0
    if vix < 13.0:
        return 0.5
    if vix < 20.0:
        return _lerp(vix, 13.0, 0.5, 20.0, 0.0)
    return _lerp(vix, 20.0, 0.0, 30.0, -0.5)


def _advance_ratio_score(adv_ratio: float) -> float:
    if adv_ratio <= 0.3:
        return -0.5
    if adv_ratio >= 0.7:
        return 0.5
    return _lerp(adv_ratio, 0.3, -0.5, 0.7, 0.5)


def _label_for_score(score: float) -> str:
    if score <= -0.6:
        return LABEL_PANIC
    if score <= -0.2:
        return LABEL_FEAR
    if score <= 0.2:
        return LABEL_NEUTRAL
    if score <= 0.6:
        return LABEL_GREED
    return LABEL_GREED_EXTREME


def compute_market_sentiment(
    indices: list[SentimentIndexQuote],
    vix: float | None,
    board_stats: BoardStats | None,
) -> QuantSentiment:
    """单市场量化情绪纯函数: 输入全部为已抓取数据, 可脱离网络/数据库单测。

    - indices: 市场内 kind=index(已排除 ^VIX)指数的涨跌幅列表, None 项不参与平均;
    - vix: ^VIX 最新价(通常仅 us 市场有), None 时该项权重让渡;
    - board_stats: 东财全板块涨跌家数合计(通常仅 cn 市场有), None 或家数全 0 时
      该项权重让渡。
    """
    changes = [quote.change_percent for quote in indices if quote.change_percent is not None]
    avg_change = sum(changes) / len(changes) if changes else None

    adv_ratio: float | None = None
    if board_stats is not None:
        total = board_stats.advance_count + board_stats.decline_count + board_stats.flat_count
        if total > 0:
            adv_ratio = board_stats.advance_count / total

    parts: list[tuple[float, float]] = []
    if avg_change is not None:
        parts.append((WEIGHT_INDEX_MOMENTUM, _momentum_score(avg_change)))
    if vix is not None:
        parts.append((WEIGHT_VIX, _vix_score(vix)))
    if adv_ratio is not None:
        parts.append((WEIGHT_ADVANCE_RATIO, _advance_ratio_score(adv_ratio)))

    inputs = {
        "avg_change_percent": avg_change,
        "vix": vix,
        "adv_ratio": adv_ratio,
    }
    if not parts:
        return QuantSentiment(score=None, label=LABEL_UNKNOWN, inputs=inputs)

    total_weight = sum(weight for weight, _ in parts)
    score = sum(weight * part_score for weight, part_score in parts) / total_weight
    return QuantSentiment(score=score, label=_label_for_score(score), inputs=inputs)
