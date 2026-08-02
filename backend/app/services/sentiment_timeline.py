"""个股情绪时间线聚合（纯读）。

把 `NewsStockMention` × `NewsItem`（限有 `sentiment_score` 的）按 Asia/Shanghai
自然日聚合成逐日情绪点，供 `GET /api/watchlist/{symbol}/sentiment-timeline` 使用。

口径：
- 聚合锚点用 `NewsItem.effective_at`（= published_at 或 fetched_at，与站内其余
  时间线/新闻排序口径一致），而非固定用 published_at，避免缺发布时间的新闻
  被整体丢弃。
- 自然日边界按 Asia/Shanghai（而非 UTC）划分——面向的是中文用户的"今天"。
- 无新闻的日期不补零点：稀疏日历留给调用方（前端）处理。
- 每日 `top_news` 按 |sentiment_score| 降序取前 3。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

MIN_DAYS = 1
MAX_DAYS = 90
DEFAULT_DAYS = 30
TOP_NEWS_PER_DAY = 3


@dataclass(frozen=True)
class TimelineNewsEntry:
    id: int
    title: str
    sentiment_label: str | None
    sentiment_score: float


@dataclass(frozen=True)
class TimelinePoint:
    date: str
    avg_score: float
    news_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    top_news: list[TimelineNewsEntry]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def clamp_days(days: int | None) -> int:
    value = days if days is not None else DEFAULT_DAYS
    return max(MIN_DAYS, min(MAX_DAYS, value))


def build_sentiment_timeline(symbol: str, days: int | None, session: Session) -> list[TimelinePoint]:
    window_days = clamp_days(days)
    window_start = datetime.now(UTC) - timedelta(days=window_days)

    stmt = (
        select(NewsItem)
        .join(NewsStockMention, NewsStockMention.news_id == NewsItem.id)
        .where(
            NewsStockMention.symbol == symbol.upper(),
            NewsItem.sentiment_score.is_not(None),
            NewsItem.effective_at >= window_start,
        )
        .order_by(NewsItem.effective_at.asc(), NewsItem.id.asc())
    )
    news_items = list(session.scalars(stmt))

    buckets: dict[str, list[NewsItem]] = defaultdict(list)
    for item in news_items:
        local_date = _as_utc(item.effective_at).astimezone(SHANGHAI_TZ).date().isoformat()
        buckets[local_date].append(item)

    points: list[TimelinePoint] = []
    for date_key in sorted(buckets):
        day_items = buckets[date_key]
        scores = [item.sentiment_score for item in day_items]
        avg_score = sum(scores) / len(scores)
        positive_count = sum(1 for item in day_items if item.sentiment_label == "positive")
        negative_count = sum(1 for item in day_items if item.sentiment_label == "negative")
        neutral_count = sum(1 for item in day_items if item.sentiment_label == "neutral")
        top_items = sorted(day_items, key=lambda item: abs(item.sentiment_score), reverse=True)[:TOP_NEWS_PER_DAY]

        points.append(
            TimelinePoint(
                date=date_key,
                avg_score=avg_score,
                news_count=len(day_items),
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                top_news=[
                    TimelineNewsEntry(
                        id=item.id,
                        title=item.title,
                        sentiment_label=item.sentiment_label,
                        sentiment_score=item.sentiment_score,
                    )
                    for item in top_items
                ],
            )
        )

    return points
