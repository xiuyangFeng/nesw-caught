"""情绪-价格背离检测（纯读）。

对单只自选股，比较「近 N 天新闻情绪均值」与「近 N 天价格变动百分比」：情绪明显
偏多但价格走弱（或反之）时判定为一次背离，供时间线 API 内嵌展示，也供
`app/workers/queue_worker.py` 的周期检查复用来触发飞书提醒。

口径：
- 情绪均值：窗口内该 symbol 关联新闻（`news_stock_mention` × 有 `sentiment_score`
  的 `news_item`）的 `sentiment_score` 算术平均；新闻数 < 3 时样本太薄，不判定
  （直接返回 None，而不是"低置信度地"给出结论）。
- 价格变动：`price_snapshot` 按 `fetched_at` 窗口内首尾两条快照的百分比变化；
  少于 2 条快照同样不判定。
- 阈值全部取 `settings.sentiment_divergence_*`（Phase 2/3 由主协调者预加进
  config.py，本模块不改 config）。

`detect_divergence` 返回值刻意做成"要么给出完整背离结果，要么 None"（而非"总是
返回一个 status 可能为 None 的对象"）：调用方（时间线 API / 周期 worker）都只关心
"这次有没有背离"，None 就是没有——语义单一，不需要在对象内部再判一次 status。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot

BEARISH_DIVERGENCE = "bearish_divergence"
BULLISH_DIVERGENCE = "bullish_divergence"

# 新闻数低于该阈值时情绪均值样本太薄，不判定。
MIN_NEWS_COUNT_FOR_SENTIMENT = 3
# window 的 API 覆盖上下限（design: `?window=` 1~14）。
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 14


@dataclass(frozen=True)
class DivergenceStatus:
    status: str
    window_days: int
    sentiment_avg: float
    news_count: int
    price_change_percent: float
    detected_at: datetime

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "window_days": self.window_days,
            "sentiment_avg": self.sentiment_avg,
            "news_count": self.news_count,
            "price_change_percent": self.price_change_percent,
            "detected_at": self.detected_at,
        }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clamp_window_days(window_days: int | None, default: int) -> int:
    value = window_days if window_days is not None else default
    return max(MIN_WINDOW_DAYS, min(MAX_WINDOW_DAYS, value))


def _sentiment_avg_and_count(symbol: str, window_start: datetime, session: Session) -> tuple[float | None, int]:
    stmt = select(NewsItem.sentiment_score).join(
        NewsStockMention, NewsStockMention.news_id == NewsItem.id
    ).where(
        NewsStockMention.symbol == symbol,
        NewsItem.sentiment_score.is_not(None),
        NewsItem.effective_at >= window_start,
    )
    scores = list(session.scalars(stmt))
    news_count = len(scores)
    if news_count < MIN_NEWS_COUNT_FOR_SENTIMENT:
        return None, news_count
    return sum(scores) / news_count, news_count


def _price_change_percent(symbol: str, window_start: datetime, session: Session) -> float | None:
    stmt = (
        select(PriceSnapshot)
        .where(PriceSnapshot.symbol == symbol, PriceSnapshot.fetched_at >= window_start)
        .order_by(PriceSnapshot.fetched_at.asc(), PriceSnapshot.id.asc())
    )
    snapshots = list(session.scalars(stmt))
    if len(snapshots) < 2:
        return None
    first_price = snapshots[0].price
    last_price = snapshots[-1].price
    if not first_price:
        return None
    return (last_price - first_price) / first_price * 100.0


def detect_divergence(symbol: str, window_days: int | None, session: Session) -> DivergenceStatus | None:
    """判定 `symbol` 近 `window_days` 天是否出现情绪-价格背离。

    - `window_days` 为 None 时取 `settings.sentiment_divergence_window_days`；
      非 None 时按 1~14 夹紧（对齐 API `?window=` 契约）。
    - 情绪样本不足 / 价格快照不足 / 未越过阈值 —— 均返回 None，不做区分（调用方
      不需要知道"为什么没有背离"，只需要知道"没有"）。
    """
    settings = get_settings()
    window = _clamp_window_days(window_days, settings.sentiment_divergence_window_days)
    now = datetime.now(UTC)
    window_start = now - timedelta(days=window)

    sentiment_avg, news_count = _sentiment_avg_and_count(symbol.upper(), window_start, session)
    if sentiment_avg is None:
        return None

    price_change_percent = _price_change_percent(symbol.upper(), window_start, session)
    if price_change_percent is None:
        return None

    min_abs_sentiment = settings.sentiment_divergence_min_abs_sentiment
    min_abs_price_change = settings.sentiment_divergence_min_abs_price_change_percent

    status: str | None = None
    if sentiment_avg >= min_abs_sentiment and price_change_percent <= -min_abs_price_change:
        status = BEARISH_DIVERGENCE
    elif sentiment_avg <= -min_abs_sentiment and price_change_percent >= min_abs_price_change:
        status = BULLISH_DIVERGENCE

    if status is None:
        return None

    return DivergenceStatus(
        status=status,
        window_days=window,
        sentiment_avg=sentiment_avg,
        news_count=news_count,
        price_change_percent=price_change_percent,
        detected_at=now,
    )
