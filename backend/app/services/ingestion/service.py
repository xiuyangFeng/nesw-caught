from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.news import NewsItemSummary
from app.services import news_ingestion
from app.services.ingestion.detail_hydration import (
    MINIMAX_SOURCE_NAME,
    hydrate_minimax_detail_items,
)
from app.services.ingestion.fetcher import fetch_source_items
from app.services.ingestion.persister import ItemPersister
from app.services.ingestion.types import (
    MAX_FETCH_WORKERS,
    RefreshSummary,
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
    SourceItem,
)
from app.services.ingestion.utils import _utc_now


class NewsIngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.source_health_repository = SourceHealthRepository(session)
        self.persister = ItemPersister(session, self.source_health_repository)

    def refresh_all(self, sources: list[SourceDefinition] | None = None) -> RefreshSummary:
        """抓取并落库一批新闻源。

        网络抓取在线程池中并发执行(纯 IO,无数据库访问);
        解析结果回到调用方线程串行落库,保证 SQLite 单写。
        """
        started_at = _utc_now()
        fetched_count = 0
        inserted_count = 0
        results: list[SourceFetchResult] = []
        inserted_items: list = []

        active_sources = [
            source for source in (sources if sources is not None else news_ingestion.load_sources()) if not source.disabled
        ]

        # 预先查出每个活跃源的本地 ETag / Last-Modified 缓存标志
        source_caches = {}
        if active_sources:
            for s in active_sources:
                health = self.source_health_repository.get_or_create(
                    source_name=s.name,
                    source_type=s.source_type,
                    market=s.market,
                )
                source_caches[s.name] = {
                    "etag": health.last_etag,
                    "last_modified": health.last_modified
                }
            self.session.commit() # 释放数据库锁以防止多线程等待时锁表

        outcomes = []
        if active_sources:
            max_workers = min(MAX_FETCH_WORKERS, len(active_sources))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-fetch") as pool:
                futures = []
                for s in active_sources:
                    cache = source_caches.get(s.name, {"etag": None, "last_modified": None})
                    futures.append(
                        pool.submit(
                            fetch_source_items,
                            s,
                            etag=cache.get("etag"),
                            last_modified=cache.get("last_modified")
                        )
                    )
                outcomes = [f.result() for f in futures]

        # 详情页水合(如 MiniMax)在落库前完成:数据库读取集中在调用方线程,
        # 详情页网络抓取在内部线程池并发执行,不占用串行落库段。
        outcomes = [self._hydrate_outcome_details(outcome) for outcome in outcomes]

        for outcome in outcomes:
            result = self.persister.persist_outcome(outcome)
            fetched_count += result.fetched_count
            inserted_count += result.inserted_count
            results.append(result)
            inserted_items.extend(result.inserted_items)

        finished_at = _utc_now()
        summary = RefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            fetched_count=fetched_count,
            inserted_count=inserted_count,
            results=results,
            inserted_items=inserted_items,
        )
        target_news_ids = [item.id for item in inserted_items]
        if target_news_ids:
            event_bus = news_ingestion.get_event_bus()
            for item in inserted_items:
                event_bus.publish(
                    "news.created",
                    NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json"),
                )
            event_bus.publish("news.created_batch", {"news_ids": target_news_ids})
        # 无新插入时不再就地处理 pending：积压由 scheduler 转交 BackgroundQueueWorker
        # 单入口处理，避免与 worker 并行重复消费（重复爬正文 + 双倍 LLM token）。
        return summary

    def _hydrate_outcome_details(self, outcome: SourceFetchOutcome) -> SourceFetchOutcome:
        """对需要详情页水合的 source(目前仅 MiniMax News)在落库前并发补全详情。"""
        if outcome.error is not None or outcome.is_not_modified or not outcome.items:
            return outcome
        if outcome.source.name != MINIMAX_SOURCE_NAME:
            return outcome
        items = hydrate_minimax_detail_items(self.session, outcome.source, outcome.items)
        return replace(outcome, items=items)

    def _refresh_source(self, source: SourceDefinition) -> SourceFetchResult:
        """单源同步刷新:抓取 + 落库。保留作测试与一次性脚本入口。"""
        health = self.source_health_repository.get_or_create(
            source_name=source.name,
            source_type=source.source_type,
            market=source.market,
        )
        outcome = fetch_source_items(source, etag=health.last_etag, last_modified=health.last_modified)
        outcome = self._hydrate_outcome_details(outcome)
        return self.persister.persist_outcome(outcome)

    def _persist_item(self, source: SourceDefinition, item: SourceItem) -> NewsItem | None:
        return self.persister.persist_item(source, item)
