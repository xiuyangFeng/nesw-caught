"""信号有效性回测服务（纯读）。

对历史新闻信号做闭环验证：回看新闻发布后一段前视时间窗内、被提及股票的
实际价格变动，聚合出利好/利空信号命中率、平均前视收益，以及按 importance
（信号置信度）/ score（情绪分数绝对值）分桶的收益与样本诊断计数。

方法学修正（Phase 2 / 工作块 E）：
- 超额收益：库内 price_snapshot 无市场指数基准快照约定（已核实，无
  index/benchmark symbol 概念），改用「同窗口内全部可评样本的平均前视收益」
  作为市场代理基准，样本级 excess_return = forward_return - benchmark_return，
  `benchmark_note` 如实说明用的是代理基准而非真实指数。
- 陈旧快照过滤：baseline 快照距新闻发布时间超过
  `settings.signal_backtest_max_snapshot_age_hours` 视为陈旧，跳过该样本并计入
  `skipped_stale_count`（是 `skipped_count` 的子集，不重复计数出候选之外）。
- 样本相关性：一条新闻提及 N 只股票产生 N 个 news x symbol 样本，彼此不独立；
  新增 `distinct_news_count` 与 `per_news_hit_rate`（先对每条新闻的命中取均值，
  再对新闻等权求均值），与逐样本 `hit_rate` 并列展示。
- 分数分桶：新增按 |sentiment_score| 的 `score_buckets`，替代信息量不足的
  importance 分桶（旧字段保留，供前端兼容）。

要点：
- 前视窗（horizon，如 1h/4h/1d）以"新闻发布时间之后最接近的 price_snapshot"
  近似；快照稀疏（缺基准价或缺前视价）时优雅降级，跳过该样本并计入 skipped。
- 库内时间统一 UTC；SQLite 读回可能是 naive datetime，比较前统一对齐到 UTC。
- 全程只读，不写库、不改 schema、不做迁移。
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_repository import MarketRepository
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.news_signal_repository import NewsSignalRepository

_HORIZON_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}
_HORIZON_PATTERN = re.compile(r"^(\d+)([mhd])$")

# importance 分桶（基于信号置信度 signal_confidence）；固定顺序，前端可稳定渲染。
_IMPORTANCE_ORDER = ["high", "medium", "low", "unknown"]

# score 分桶边界（基于 |sentiment_score|）；固定顺序，前端可稳定渲染。
_SCORE_BUCKET_BOUNDS = (0.2, 0.4, 0.6, 0.8)
_SCORE_BUCKET_LABELS = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]


def parse_horizon(horizon: str) -> timedelta:
    """解析前视窗表达式（如 '1h' / '4h' / '1d' / '30m'）为 timedelta。

    非法输入抛 ValueError，由路由转换为 400。
    """
    match = _HORIZON_PATTERN.match((horizon or "").strip().lower())
    if match is None:
        raise ValueError(f"invalid horizon: {horizon!r}")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError(f"invalid horizon: {horizon!r}")
    return timedelta(seconds=amount * _HORIZON_UNIT_SECONDS[match.group(2)])


def _as_utc(value: datetime) -> datetime:
    """将（可能为 naive 的）datetime 对齐到 UTC。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _importance_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.66:
        return "high"
    if confidence >= 0.33:
        return "medium"
    return "low"


def _score_bucket_label(abs_score: float) -> str:
    """按 |sentiment_score| 落桶，边界 0.2/0.4/0.6/0.8（含左不含右，末桶含右端 1.0）。"""
    clamped = max(0.0, min(abs_score, 1.0))
    lower = 0.0
    for bound in _SCORE_BUCKET_BOUNDS:
        if clamped < bound:
            return f"{lower:.1f}-{bound:.1f}"
        lower = bound
    return f"{lower:.1f}-1.0"


def _baseline_snapshot(
    snapshots: list[PriceSnapshot], times: list[datetime], published_at: datetime
) -> PriceSnapshot | None:
    """发布时点/之前最近一条快照；无则 None。"""
    index = bisect_right(times, published_at) - 1
    if index < 0:
        return None
    return snapshots[index]


def _forward_price(
    snapshots: list[PriceSnapshot],
    times: list[datetime],
    published_at: datetime,
    horizon: timedelta,
) -> float | None:
    """发布时间 + horizon 之后最接近的一条快照价格；无则 None（稀疏降级）。

    取第一条 fetched_at >= target 的快照，即目标时点之后最接近的一条。
    """
    target = published_at + horizon
    index = bisect_left(times, target)
    if index >= len(times):
        return None
    return snapshots[index].price


class SignalBacktestService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.signal_repo = NewsSignalRepository(session)
        self.mentions_repo = NewsMentionsRepository(session)
        self.market_repo = MarketRepository(session)

    def run(
        self,
        *,
        market: str | None = None,
        window_days: int = 30,
        horizon: str = "1d",
        now: datetime | None = None,
    ) -> dict:
        horizon_delta = parse_horizon(horizon)
        current = _as_utc(now) if now is not None else datetime.now(UTC)
        since = current - timedelta(days=window_days)
        max_snapshot_age_hours = get_settings().signal_backtest_max_snapshot_age_hours

        news_list = self.signal_repo.list_directional_signal_news(market=market, since=since)
        news_by_id: dict[int, NewsItem] = {news.id: news for news in news_list}
        news_ids = list(news_by_id.keys())

        mentions = self.mentions_repo.list_mentions_for_news(news_ids)
        signal_map = self.signal_repo.get_signal_result_map(news_ids)

        symbols = sorted({mention.symbol for mention in mentions})
        snapshots_by_symbol = self.market_repo.list_snapshots_by_symbols(symbols)
        times_by_symbol: dict[str, list[datetime]] = {
            symbol: [_as_utc(snapshot.fetched_at) for snapshot in snapshots]
            for symbol, snapshots in snapshots_by_symbol.items()
        }

        total_signals = 0
        skipped_count = 0
        skipped_stale_count = 0
        # 可评样本明细（用于二次聚合：方向 / importance 桶 / score 桶 / per-news）。
        evaluable_samples: list[dict] = []

        for mention in mentions:
            news = news_by_id.get(mention.news_id)
            if news is None:
                continue
            label = news.sentiment_label
            if label not in ("positive", "negative"):
                continue

            total_signals += 1

            snapshots = snapshots_by_symbol.get(mention.symbol)
            times = times_by_symbol.get(mention.symbol)
            if not snapshots or not times:
                skipped_count += 1
                continue

            published_at = _as_utc(news.published_at)
            baseline_snapshot = _baseline_snapshot(snapshots, times, published_at)
            if baseline_snapshot is None:
                skipped_count += 1
                continue

            baseline_time = _as_utc(baseline_snapshot.fetched_at)
            age_hours = (published_at - baseline_time).total_seconds() / 3600.0
            if age_hours > max_snapshot_age_hours:
                skipped_count += 1
                skipped_stale_count += 1
                continue

            baseline_price = baseline_snapshot.price
            forward_price = _forward_price(snapshots, times, published_at, horizon_delta)
            if forward_price is None or baseline_price == 0:
                skipped_count += 1
                continue

            forward_return = (forward_price - baseline_price) / baseline_price
            hit = (label == "positive" and forward_return > 0) or (
                label == "negative" and forward_return < 0
            )

            signal = signal_map.get(mention.news_id)
            confidence = signal.signal_confidence if signal is not None else None
            abs_score = abs(news.sentiment_score) if news.sentiment_score is not None else 0.0

            evaluable_samples.append(
                {
                    "news_id": mention.news_id,
                    "symbol": mention.symbol,
                    "label": label,
                    "forward_return": forward_return,
                    "hit": hit,
                    "importance_bucket": _importance_bucket(confidence),
                    "score_bucket": _score_bucket_label(abs_score),
                }
            )

        # 代理市场基准：同窗口 + 同 horizon 内全部可评样本的平均前视收益。
        # 库内 price_snapshot 未提供指数类 symbol 的基准快照约定，禁止假装有真实基准。
        if evaluable_samples:
            benchmark_return = sum(s["forward_return"] for s in evaluable_samples) / len(
                evaluable_samples
            )
            benchmark_note = (
                "price_snapshot 未提供市场指数基准快照，采用同窗口内全部可评样本的"
                "平均前视收益（forward_return）作为市场代理基准（proxy benchmark），"
                "而非真实指数收益。"
            )
        else:
            benchmark_return = None
            benchmark_note = "窗口内无可评样本，无法计算代理基准；excess_return 均为 null。"

        for sample in evaluable_samples:
            sample["excess_return"] = (
                sample["forward_return"] - benchmark_return if benchmark_return is not None else None
            )

        evaluable_count = len(evaluable_samples)
        evaluable_rate = round(evaluable_count / total_signals, 4) if total_signals else None

        positive_samples = [s for s in evaluable_samples if s["label"] == "positive"]
        negative_samples = [s for s in evaluable_samples if s["label"] == "negative"]

        importance_bucket_samples: dict[str, list[dict]] = {name: [] for name in _IMPORTANCE_ORDER}
        score_bucket_samples: dict[str, list[dict]] = {name: [] for name in _SCORE_BUCKET_LABELS}
        for sample in evaluable_samples:
            importance_bucket_samples[sample["importance_bucket"]].append(sample)
            score_bucket_samples[sample["score_bucket"]].append(sample)

        news_hits: dict[int, list[bool]] = defaultdict(list)
        for sample in evaluable_samples:
            news_hits[sample["news_id"]].append(sample["hit"])
        distinct_news_count = len(news_hits)
        per_news_rates = [sum(1 for h in hits if h) / len(hits) for hits in news_hits.values()]
        per_news_hit_rate = round(sum(per_news_rates) / len(per_news_rates), 4) if per_news_rates else None

        all_excess_returns = [s["excess_return"] for s in evaluable_samples if s["excess_return"] is not None]
        avg_excess_return = (
            round(sum(all_excess_returns) / len(all_excess_returns), 6) if all_excess_returns else None
        )

        return {
            "market": market,
            "window_days": window_days,
            "horizon": horizon,
            "generated_at": current,
            "total_signals": total_signals,
            "evaluable_count": evaluable_count,
            "skipped_count": skipped_count,
            "skipped_stale_count": skipped_stale_count,
            "evaluable_rate": evaluable_rate,
            "benchmark_return": round(benchmark_return, 6) if benchmark_return is not None else None,
            "benchmark_note": benchmark_note,
            "avg_excess_return": avg_excess_return,
            "distinct_news_count": distinct_news_count,
            "per_news_hit_rate": per_news_hit_rate,
            "positive": _direction_view("positive", positive_samples),
            "negative": _direction_view("negative", negative_samples),
            "importance_buckets": _bucket_views(importance_bucket_samples),
            "score_buckets": _score_bucket_views(score_bucket_samples),
        }


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _direction_view(label: str, samples: list[dict]) -> dict:
    sample_count = len(samples)
    hit_count = sum(1 for s in samples if s["hit"])
    forward_returns = [s["forward_return"] for s in samples]
    excess_returns = [s["excess_return"] for s in samples if s["excess_return"] is not None]
    avg_forward = _avg(forward_returns)
    avg_excess = _avg(excess_returns)
    return {
        "label": label,
        "sample_count": sample_count,
        "hit_count": hit_count,
        "hit_rate": round(hit_count / sample_count, 4) if sample_count else None,
        "avg_forward_return": round(avg_forward, 6) if avg_forward is not None else None,
        "avg_excess_return": round(avg_excess, 6) if avg_excess is not None else None,
    }


def _bucket_views(bucket_samples: dict[str, list[dict]]) -> list[dict]:
    views: list[dict] = []
    for name in _IMPORTANCE_ORDER:
        samples = bucket_samples[name]
        # high/medium/low 始终输出（便于前端稳定渲染），unknown 仅在有样本时输出。
        if name == "unknown" and not samples:
            continue
        sample_count = len(samples)
        forward_returns = [s["forward_return"] for s in samples]
        excess_returns = [s["excess_return"] for s in samples if s["excess_return"] is not None]
        avg_forward = _avg(forward_returns)
        avg_excess = _avg(excess_returns)
        views.append(
            {
                "bucket": name,
                "sample_count": sample_count,
                "avg_forward_return": round(avg_forward, 6) if avg_forward is not None else None,
                "avg_excess_return": round(avg_excess, 6) if avg_excess is not None else None,
            }
        )
    return views


def _score_bucket_views(bucket_samples: dict[str, list[dict]]) -> list[dict]:
    views: list[dict] = []
    for label in _SCORE_BUCKET_LABELS:
        samples = bucket_samples[label]
        sample_count = len(samples)
        hit_count = sum(1 for s in samples if s["hit"])
        forward_returns = [s["forward_return"] for s in samples]
        excess_returns = [s["excess_return"] for s in samples if s["excess_return"] is not None]
        avg_forward = _avg(forward_returns)
        avg_excess = _avg(excess_returns)
        views.append(
            {
                "range_label": label,
                "sample_count": sample_count,
                "hit_rate": round(hit_count / sample_count, 4) if sample_count else None,
                "avg_forward_return": round(avg_forward, 6) if avg_forward is not None else None,
                "avg_excess_return": round(avg_excess, 6) if avg_excess is not None else None,
            }
        )
    return views
