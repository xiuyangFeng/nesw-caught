from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.source_health import NewsRuntimeMarketView, NewsRuntimeSourceView, NewsRuntimeView
from app.services.event_bus import get_event_bus
from app.services.news_ingestion import load_sources

# 每个 (源, 市场) 的最新新闻只需要这几列，不再 hydrate 整个 NewsItem ORM 对象；
# 这里拿到的是 SQLAlchemy Row（id / source_name / market / published_at / fetched_at）。
_LatestNewsFact = Any

RECENT_INCREMENTAL_WINDOW = timedelta(minutes=5)
RECENT_MARKET_NEWS_WINDOW = timedelta(minutes=30)
RECENT_PRIMARY_SUCCESS_WINDOW = timedelta(minutes=15)
RECENT_SOURCE_MODE_WINDOW = timedelta(minutes=30)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _source_status(*, now: datetime, last_success_at: datetime | None, consecutive_failures: int, cadence_seconds: int) -> str:
    if consecutive_failures >= 4:
        return "offline"
    if consecutive_failures >= 2:
        return "degraded"
    if last_success_at is None:
        return "offline"
    if now - last_success_at > timedelta(seconds=cadence_seconds * 2):
        return "delayed"
    return "ok"


def _market_mode(*, now: datetime, source_facts: list[dict[str, object]]) -> str:
    recent_threshold = now - RECENT_SOURCE_MODE_WINDOW
    for tier in ("primary", "secondary", "fallback"):
        recent_successes = [
            item["last_success_at"]
            for item in source_facts
            if item["tier"] == tier
            and item["last_success_at"] is not None
            and item["last_success_at"] >= recent_threshold
        ]
        if recent_successes:
            return tier
    return "none"


class NewsRuntimeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.source_health_repository = SourceHealthRepository(session)

    def build(self) -> NewsRuntimeView:
        now = _utc_now()
        source_health_rows = self.source_health_repository.list_all()
        source_definitions = {
            (source.name, market): source
            for source in load_sources()
            for market in (source.markets or [source.market])
        }
        enabled_markets = sorted(
            {
                market
                for source in source_definitions.values()
                if not source.disabled
                for market in (source.markets or [source.market])
            }
        )
        source_keys = {(row.source_name, row.market) for row in source_health_rows}

        latest_news_by_source: dict[tuple[str, str], _LatestNewsFact] = {}
        if source_keys:
            # SQL 聚合替代全表物化：先按 (source_name, market) GROUP BY 取 MAX(fetched_at)，
            # 再回表取该行字段；物化行数从 N 降到“表内 (源, 市场) 组合数 + 并列行”。
            #
            # 两点让它能吃到 (source_name, market, fetched_at) 复合索引：
            # 1) 分组键与 MAX() 的列都是裸列，没有函数包裹（lower()/date() 之类会直接
            #    让 SQLite 放弃索引，退化成全表扫 + 临时 B 树）；
            # 2) 先按在册的源名 / 市场把行数收窄，再做 GROUP BY——此前对整张 news_item
            #    分组，连早已下线的历史源都要参与聚合。
            known_source_names = sorted({name for name, _ in source_keys})
            known_markets = sorted({market for _, market in source_keys})
            latest_per_source = (
                select(
                    NewsItem.source_name.label("source_name"),
                    NewsItem.market.label("market"),
                    func.max(NewsItem.fetched_at).label("max_fetched_at"),
                )
                .where(
                    NewsItem.source_name.in_(known_source_names),
                    NewsItem.market.in_(known_markets),
                )
                .group_by(NewsItem.source_name, NewsItem.market)
                .subquery()
            )
            # 只取需要的列，避免为每个 (源, 市场) 组合 hydrate 一整个 ORM 对象
            # （含 summary / ai_takeaway / signal_error 三个 Text 列）。
            stmt = select(
                NewsItem.id,
                NewsItem.source_name,
                NewsItem.market,
                NewsItem.published_at,
                NewsItem.fetched_at,
            ).join(
                latest_per_source,
                and_(
                    NewsItem.source_name == latest_per_source.c.source_name,
                    NewsItem.market == latest_per_source.c.market,
                    NewsItem.fetched_at == latest_per_source.c.max_fetched_at,
                ),
            )
            for row in self.session.execute(stmt):
                source_key = (row.source_name, row.market)
                if source_key not in source_keys:
                    continue
                # fetched_at 并列时 join 会带回多行，与旧算法（id DESC）一致取大 id
                existing = latest_news_by_source.get(source_key)
                if existing is None or row.id > existing.id:
                    latest_news_by_source[source_key] = row

        # 市场最新 = 各在册源最新行中 (fetched_at, id) 最大者，与旧全表折叠算法等价
        latest_news_by_market: dict[str, _LatestNewsFact] = {}
        for row in latest_news_by_source.values():
            existing = latest_news_by_market.get(row.market)
            if existing is None or (row.fetched_at, row.id) > (existing.fetched_at, existing.id):
                latest_news_by_market[row.market] = row

        source_views: list[NewsRuntimeSourceView] = []
        market_source_facts: dict[str, list[dict[str, object]]] = defaultdict(list)
        for health in source_health_rows:
            source_definition = source_definitions.get((health.source_name, health.market))
            tier = source_definition.tier if source_definition is not None else "primary"
            cadence_seconds = source_definition.cadence_seconds if source_definition is not None else 300
            last_success_at = _normalize_utc(health.last_success_at)
            last_failure_at = _normalize_utc(health.last_failure_at)
            last_attempt_at = max(filter(None, [last_success_at, last_failure_at]), default=None)
            status = _source_status(
                now=now,
                last_success_at=last_success_at,
                consecutive_failures=health.consecutive_failures,
                cadence_seconds=cadence_seconds,
            )
            latest_news = latest_news_by_source.get((health.source_name, health.market))
            source_views.append(
                NewsRuntimeSourceView(
                    source_name=health.source_name,
                    market=health.market,
                    tier=tier,
                    status=status,
                    last_attempt_at=last_attempt_at,
                    last_success_at=last_success_at,
                    consecutive_failures=health.consecutive_failures,
                    avg_fetch_latency_ms=health.avg_latency_ms,
                    latest_news_published_at=_normalize_utc(latest_news.published_at) if latest_news else None,
                    latest_news_fetched_at=_normalize_utc(latest_news.fetched_at) if latest_news else None,
                    last_error=None,
                )
            )
            market_source_facts[health.market].append(
                {
                    "tier": tier,
                    "status": status,
                    "last_success_at": last_success_at,
                }
            )

        source_views.sort(key=lambda item: (item.market, item.source_name))

        last_refresh_finished_at = max(
            (_normalize_utc(health.last_success_at) for health in source_health_rows if health.last_success_at is not None),
            default=None,
        )

        market_views: list[NewsRuntimeMarketView] = []
        degraded_market_count = 0
        for market in enabled_markets:
            facts = market_source_facts.get(market, [])
            latest_market_news = latest_news_by_market.get(market)
            last_news_created_at = _normalize_utc(latest_market_news.fetched_at) if latest_market_news else None
            last_primary_success_at = max(
                (fact["last_success_at"] for fact in facts if fact["tier"] == "primary" and fact["last_success_at"] is not None),
                default=None,
            )
            has_recent_primary_success = (
                last_primary_success_at is not None
                and last_primary_success_at >= now - RECENT_PRIMARY_SUCCESS_WINDOW
            )
            has_recent_market_news = (
                last_news_created_at is not None
                and last_news_created_at >= now - RECENT_MARKET_NEWS_WINDOW
            )
            has_recent_non_primary_success = any(
                fact["tier"] in {"secondary", "fallback"}
                and fact["last_success_at"] is not None
                and fact["last_success_at"] >= now - RECENT_SOURCE_MODE_WINDOW
                for fact in facts
            )
            primary_problem = any(
                fact["tier"] == "primary" and fact["status"] in {"degraded", "offline"}
                for fact in facts
            )
            any_recent_success = any(
                fact["last_success_at"] is not None
                and fact["last_success_at"] >= now - RECENT_SOURCE_MODE_WINDOW
                for fact in facts
            )

            if not any_recent_success:
                status = "offline"
                degraded_reason = "no source succeeded within 30 minutes"
            elif primary_problem and has_recent_non_primary_success:
                status = "degraded"
                degraded_reason = "primary sources failing; fallback supply active"
            elif has_recent_primary_success and has_recent_market_news:
                status = "live"
                degraded_reason = None
            else:
                status = "delayed"
                degraded_reason = None

            if status in {"degraded", "offline"}:
                degraded_market_count += 1

            market_views.append(
                NewsRuntimeMarketView(
                    market=market,
                    status=status,
                    mode=_market_mode(now=now, source_facts=facts),
                    last_primary_success_at=last_primary_success_at,
                    last_news_created_at=last_news_created_at,
                    degraded_reason=degraded_reason,
                )
            )

        bus_status = get_event_bus().get_status()
        last_incremental_event_at = (
            _normalize_utc(bus_status.last_published_at)
            if bus_status.last_event_name in {"news.created", "news.updated"}
            else None
        )
        last_news_created_at = max(
            (_normalize_utc(item.fetched_at) for item in latest_news_by_market.values() if item.fetched_at is not None),
            default=None,
        )

        if any(item.status in {"degraded", "offline"} for item in market_views):
            feed_status = "degraded"
        elif (
            market_views
            and all(item.status == "live" for item in market_views)
            and last_incremental_event_at is not None
            and last_incremental_event_at >= now - RECENT_INCREMENTAL_WINDOW
        ):
            feed_status = "live"
        else:
            feed_status = "delayed"

        return NewsRuntimeView(
            feed_status=feed_status,
            last_refresh_finished_at=_normalize_utc(last_refresh_finished_at),
            last_news_created_at=last_news_created_at,
            last_incremental_event_at=last_incremental_event_at,
            degraded_market_count=degraded_market_count,
            markets=market_views,
            sources=source_views,
        )
