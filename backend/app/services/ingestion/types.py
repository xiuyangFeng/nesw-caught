from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from app.models.news_item import NewsItem

SourceType = Literal["rss", "html", "api"]
VALID_SOURCE_TIERS = {"primary", "secondary", "fallback"}
VALID_SOURCE_TYPES = {"rss", "html", "api"}
SOURCE_TIER_RANKS = {"primary": 3, "secondary": 2, "fallback": 1}

# 抓取并发上限:网络 IO 并发执行,但数据库写入始终在调用方线程串行完成(SQLite 单写约束)。
MAX_FETCH_WORKERS = 8
# 去重滑动窗口:同主机+同规范化标题,发布时间相差 ±60 分钟以内视为同一条新闻。
DUPLICATE_WINDOW = timedelta(minutes=60)
# 平均时延采用指数移动平均(EMA),避免 (old+new)/2 的伪平均。
LATENCY_EMA_ALPHA = 0.3


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    source_type: SourceType
    url: str
    market: str
    tier: str = "primary"
    priority: int = 100
    cadence_seconds: int = 300
    markets: list[str] | None = None
    supports_incremental: bool = False
    language: str | None = None
    parser: str = "rss"
    item_limit: int = 20
    entry_selector: str | None = None
    title_selector: str | None = None
    link_selector: str | None = None
    time_selector: str | None = None
    content_selector: str | None = None
    disabled: bool = False


@dataclass(frozen=True)
class SourceItem:
    title: str
    canonical_url: str
    summary: str | None
    content_text: str | None
    published_at: datetime | None
    content_html: str | None = None
    extract_status: str | None = None
    extract_error: str | None = None


@dataclass(frozen=True)
class SourceFetchOutcome:
    """网络抓取阶段的产物,不携带任何数据库状态,可安全跨线程传递。"""

    source: SourceDefinition
    items: list[SourceItem]
    error: str | None
    latency_ms: float


@dataclass(frozen=True)
class SourceFetchResult:
    source_name: str
    source_type: str
    status: str
    fetched_count: int
    inserted_count: int
    error: str | None
    latency_ms: float
    inserted_items: list[NewsItem] = field(default_factory=list)


@dataclass(frozen=True)
class RefreshSummary:
    started_at: datetime
    finished_at: datetime
    fetched_count: int
    inserted_count: int
    results: list[SourceFetchResult]
    inserted_items: list[NewsItem] = field(default_factory=list)
