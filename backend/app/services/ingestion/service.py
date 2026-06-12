from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.news import NewsItemSummary
from app.services import news_ingestion
from app.services.ingestion.fetcher import fetch_source_items
from app.services.ingestion.persister import ItemPersister
from app.models.news_item import NewsItem
from app.services.ingestion.types import (
    MAX_FETCH_WORKERS,
    RefreshSummary,
    SourceDefinition,
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
        outcomes = []
        if active_sources:
            max_workers = min(MAX_FETCH_WORKERS, len(active_sources))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-fetch") as pool:
                outcomes = list(pool.map(fetch_source_items, active_sources))

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
        else:
            pipeline = news_ingestion.NewsSignalPipelineService(self.session)
            target_news_ids = pipeline.list_pending_news_ids(limit=50)
            if target_news_ids:
                pipeline.process_news_ids(target_news_ids)
                self.session.commit()
        return summary

    def _refresh_source(self, source: SourceDefinition) -> SourceFetchResult:
        """单源同步刷新:抓取 + 落库。保留作测试与一次性脚本入口。"""
        return self.persister.persist_outcome(fetch_source_items(source))

    def _persist_item(self, source: SourceDefinition, item: SourceItem) -> NewsItem | None:
        return self.persister.persist_item(source, item)
