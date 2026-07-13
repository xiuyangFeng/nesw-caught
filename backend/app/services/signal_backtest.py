"""信号有效性回测服务（纯读）。

对历史新闻信号做闭环验证：回看新闻发布后一段前视时间窗内、被提及股票的
实际价格变动，聚合出利好/利空信号命中率、平均前视收益，以及按 importance
（信号置信度）分桶的收益与样本诊断计数。

要点：
- 前视窗（horizon，如 1h/4h/1d）以"新闻发布时间之后最接近的 price_snapshot"
  近似；快照稀疏（缺基准价或缺前视价）时优雅降级，跳过该样本并计入 skipped。
- 库内时间统一 UTC；SQLite 读回可能是 naive datetime，比较前统一对齐到 UTC。
- 全程只读，不写库、不改 schema、不做迁移。
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_repository import MarketRepository
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.news_signal_repository import NewsSignalRepository

_HORIZON_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}
_HORIZON_PATTERN = re.compile(r"^(\d+)([mhd])$")

# importance 分桶（基于信号置信度 signal_confidence）；固定顺序，前端可稳定渲染。
_IMPORTANCE_ORDER = ["high", "medium", "low", "unknown"]


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
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _importance_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.66:
        return "high"
    if confidence >= 0.33:
        return "medium"
    return "low"


def _baseline_price(snapshots: list[PriceSnapshot], times: list[datetime], published_at: datetime) -> float | None:
    """发布时点/之前最近一条快照的价格；无则 None。"""
    index = bisect_right(times, published_at) - 1
    if index < 0:
        return None
    return snapshots[index].price


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
        current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
        since = current - timedelta(days=window_days)

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
        # 方向聚合：{label: {"returns": [...], "hits": int}}
        direction_stats: dict[str, dict] = {
            "positive": {"returns": [], "hits": 0},
            "negative": {"returns": [], "hits": 0},
        }
        # importance 分桶：{bucket: [returns]}
        bucket_returns: dict[str, list[float]] = {name: [] for name in _IMPORTANCE_ORDER}

        for mention in mentions:
            news = news_by_id.get(mention.news_id)
            if news is None:
                continue
            label = news.sentiment_label
            if label not in direction_stats:
                continue

            total_signals += 1

            snapshots = snapshots_by_symbol.get(mention.symbol)
            times = times_by_symbol.get(mention.symbol)
            if not snapshots or not times:
                skipped_count += 1
                continue

            published_at = _as_utc(news.published_at)
            baseline = _baseline_price(snapshots, times, published_at)
            forward = _forward_price(snapshots, times, published_at, horizon_delta)
            if baseline is None or forward is None or baseline == 0:
                skipped_count += 1
                continue

            forward_return = (forward - baseline) / baseline

            stats = direction_stats[label]
            stats["returns"].append(forward_return)
            if (label == "positive" and forward_return > 0) or (label == "negative" and forward_return < 0):
                stats["hits"] += 1

            signal = signal_map.get(mention.news_id)
            confidence = signal.signal_confidence if signal is not None else None
            bucket_returns[_importance_bucket(confidence)].append(forward_return)

        evaluable_count = len(direction_stats["positive"]["returns"]) + len(direction_stats["negative"]["returns"])
        evaluable_rate = round(evaluable_count / total_signals, 4) if total_signals else None

        return {
            "market": market,
            "window_days": window_days,
            "horizon": horizon,
            "generated_at": current,
            "total_signals": total_signals,
            "evaluable_count": evaluable_count,
            "skipped_count": skipped_count,
            "evaluable_rate": evaluable_rate,
            "positive": _direction_view("positive", direction_stats["positive"]),
            "negative": _direction_view("negative", direction_stats["negative"]),
            "importance_buckets": _bucket_views(bucket_returns),
        }


def _direction_view(label: str, stats: dict) -> dict:
    returns: list[float] = stats["returns"]
    sample_count = len(returns)
    hit_count = stats["hits"]
    return {
        "label": label,
        "sample_count": sample_count,
        "hit_count": hit_count,
        "hit_rate": round(hit_count / sample_count, 4) if sample_count else None,
        "avg_forward_return": round(sum(returns) / sample_count, 6) if sample_count else None,
    }


def _bucket_views(bucket_returns: dict[str, list[float]]) -> list[dict]:
    views: list[dict] = []
    for name in _IMPORTANCE_ORDER:
        returns = bucket_returns[name]
        # high/medium/low 始终输出（便于前端稳定轴），unknown 仅在有样本时输出。
        if name == "unknown" and not returns:
            continue
        sample_count = len(returns)
        views.append(
            {
                "bucket": name,
                "sample_count": sample_count,
                "avg_forward_return": round(sum(returns) / sample_count, 6) if sample_count else None,
            }
        )
    return views
