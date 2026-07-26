from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

from sqlalchemy.orm import Session

from app.core.config import get_settings
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

logger = logging.getLogger(__name__)


def _fetch_max_workers() -> int:
    """抓取并发上限:优先读配置,配置不可用时退回模块级默认常量。"""
    try:
        return max(int(get_settings().news_fetch_max_workers), 1)
    except Exception:  # pragma: no cover - 配置不可用是极端情况
        return MAX_FETCH_WORKERS


class NewsIngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.source_health_repository = SourceHealthRepository(session)
        self.persister = ItemPersister(session, self.source_health_repository)

    def refresh_all(self, sources: list[SourceDefinition] | None = None) -> RefreshSummary:
        """抓取并落库一批新闻源。

        网络抓取在线程池中并发执行(纯 IO,无数据库访问);
        解析结果回到调用方线程串行落库,保证 SQLite 单写。

        时效性关键点(2026-07-25):此前是 `[f.result() for f in futures]` 的整批
        栅栏——所有源都要等最慢的那个返回才开始落库,并且要等全部源落库完成才
        统一 publish 事件,于是第一个返回的源的新闻要陪跑到最后一个源。现在改为
        `as_completed`:谁先回来谁先水合、先落库、先发事件。落库仍然串行在调用方
        线程(SQLite 单写约束不变)。
        """
        started_at = _utc_now()
        fetched_count = 0
        inserted_count = 0
        results: list[SourceFetchResult] = []
        inserted_items: list = []

        active_sources = [
            source for source in (sources if sources is not None else news_ingestion.load_sources()) if not source.disabled
        ]
        logger.info("news ingestion cycle started: active_sources=%s", len(active_sources))

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

        if active_sources:
            max_workers = min(_fetch_max_workers(), len(active_sources))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-fetch") as pool:
                futures = {}
                for s in active_sources:
                    cache = source_caches.get(s.name, {"etag": None, "last_modified": None})
                    future = pool.submit(
                        fetch_source_items,
                        s,
                        etag=cache.get("etag"),
                        last_modified=cache.get("last_modified"),
                    )
                    futures[future] = s
                for future in as_completed(futures):
                    outcome = future.result()
                    source_started = time.perf_counter()
                    # 详情页水合(如 MiniMax)在落库前完成:数据库读取集中在调用方线程,
                    # 详情页网络抓取在内部线程池并发执行,不占用串行落库段。
                    outcome = self._hydrate_outcome_details(outcome)
                    result = self.persister.persist_outcome(outcome)
                    fetched_count += result.fetched_count
                    inserted_count += result.inserted_count
                    results.append(result)
                    inserted_items.extend(result.inserted_items)
                    # 落库即发事件:不再等其余源,SSE 前端与分析队列都能第一时间拿到。
                    self._publish_inserted(result.inserted_items)
                    if result.inserted_count:
                        logger.info(
                            "source persisted: name=%s status=%s fetched=%s inserted=%s "
                            "fetch_latency_ms=%.1f persist_ms=%.1f",
                            result.source_name,
                            result.status,
                            result.fetched_count,
                            result.inserted_count,
                            result.latency_ms,
                            (time.perf_counter() - source_started) * 1000,
                        )

        finished_at = _utc_now()
        elapsed_ms = round((finished_at - started_at).total_seconds() * 1000, 2)
        logger.info(
            "news ingestion cycle finished: active_sources=%s fetched=%s inserted=%s elapsed_ms=%s",
            len(active_sources),
            fetched_count,
            inserted_count,
            elapsed_ms,
        )
        summary = RefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            fetched_count=fetched_count,
            inserted_count=inserted_count,
            results=results,
            inserted_items=inserted_items,
        )
        # 事件已在每个源落库后就地发布(见上方 _publish_inserted),这里不再重复发布。
        # 无新插入时不再就地处理 pending：积压由 scheduler 转交 BackgroundQueueWorker
        # 单入口处理，避免与 worker 并行重复消费（重复爬正文 + 双倍 LLM token）。
        return summary

    def _publish_inserted(self, inserted_items: list[NewsItem]) -> None:
        """按源发布 `news.created`(逐条,SSE 前端依赖) + `news.created_batch`(整块)。

        逐条 publish 在 hybrid 后端下是 N 次 Redis XADD;"Redis 可达但慢"时既不会
        触发按连续失败计数的熔断,又会把串行落库线程卡住 N * socket_timeout 秒。
        因此优先走事件总线的 `publish_batch`——内存总线仍然逐条投递(前端行为不变),
        Redis 这一跳有整体时间预算,超预算即对本批剩余条目降级为"只走内存总线"。
        只实现了 publish() 的测试替身会自动回退到逐条发布。
        """
        if not inserted_items:
            return
        event_bus = news_ingestion.get_event_bus()
        payloads = [
            NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json")
            for item in inserted_items
        ]
        publish_batch = getattr(event_bus, "publish_batch", None)
        if callable(publish_batch):
            publish_batch("news.created", payloads)
        else:
            for payload in payloads:
                event_bus.publish("news.created", payload)
        event_bus.publish("news.created_batch", {"news_ids": [item.id for item in inserted_items]})

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
