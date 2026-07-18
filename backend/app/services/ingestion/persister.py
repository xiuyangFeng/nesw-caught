from __future__ import annotations

import logging
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.dedup_gate import DuplicateGate
from app.services.ingestion.sources import _should_promote_source_metadata
from app.services.ingestion.types import (
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
    SourceItem,
)
from app.services.ingestion.utils import _ema_latency, _utc_now
from app.services.news_priority import passes_ingest_relevance_gate

logger = logging.getLogger(__name__)


class ItemPersister:
    def __init__(self, session: Session, source_health_repository: SourceHealthRepository) -> None:
        self.session = session
        self.source_health_repository = source_health_repository
        self.duplicate_gate = DuplicateGate(session)

    def persist_outcome(self, outcome: SourceFetchOutcome) -> SourceFetchResult:
        """串行落库阶段:健康度记账 + 入库。必须在持有 session 的线程中调用。"""
        source = outcome.source
        health = self.source_health_repository.get_or_create(
            source_name=source.name,
            source_type=source.source_type,
            market=source.market,
        )
        health.total_fetches += 1
        health.last_http_status = outcome.http_status

        if outcome.error is not None:
            status = outcome.error_kind if outcome.error_kind in {"http_error", "parse_error"} else "http_error"
            return self.record_failure(
                source,
                error=outcome.error,
                latency_ms=outcome.latency_ms,
                status=status,
                http_status=outcome.http_status,
            )

        # 保存最新的 ETag / Last-Modified 缓存标头
        health.last_etag = outcome.etag
        health.last_modified = outcome.last_modified

        if outcome.is_not_modified:
            health.last_success_at = _utc_now()
            health.consecutive_failures = 0
            health.consecutive_empty_batches = 0
            health.last_status = "not_modified"
            health.last_error = None
            health.last_fetched_count = 0
            health.last_inserted_count = 0
            health.avg_latency_ms = _ema_latency(health.avg_latency_ms, outcome.latency_ms)
            self.session.commit()
            return SourceFetchResult(
                source_name=source.name,
                source_type=source.source_type,
                status="not_modified",
                fetched_count=0,
                inserted_count=0,
                error=None,
                latency_ms=outcome.latency_ms,
                inserted_items=[],
            )

        try:
            items = outcome.items
            # 详情页水合(如 MiniMax)已挪到并发抓取阶段(service._hydrate_outcome_details),
            # 本串行落库段不再发任何 HTTP 请求。
            if not items:
                health.consecutive_empty_batches += 1
                health.consecutive_failures = 0
                health.last_status = "empty"
                health.last_error = "parsed 0 items"
                health.last_fetched_count = 0
                health.last_inserted_count = 0
                health.avg_latency_ms = _ema_latency(health.avg_latency_ms, outcome.latency_ms)
                self.session.commit()
                return SourceFetchResult(
                    source_name=source.name,
                    source_type=source.source_type,
                    status="empty",
                    fetched_count=0,
                    inserted_count=0,
                    error="parsed 0 items",
                    latency_ms=outcome.latency_ms,
                    inserted_items=[],
                )

            inserted_count = 0
            inserted_items: list[NewsItem] = []
            # 按批预取去重候选:一次范围查询建立签名索引,整批复用,
            # 避免每条 item 触发一次 ±60 分钟窗口的完整 ORM 全量加载。
            self.duplicate_gate.prime(items)
            try:
                for item in items:
                    inserted_item = self.persist_item(source, item)
                    if inserted_item is not None:
                        inserted_count += 1
                        inserted_items.append(inserted_item)
            finally:
                self.duplicate_gate.invalidate()

            health.last_success_at = _utc_now()
            health.consecutive_failures = 0
            health.consecutive_empty_batches = 0
            health.last_status = "ok"
            health.last_error = None
            health.last_fetched_count = len(items)
            health.last_inserted_count = inserted_count
            health.avg_latency_ms = _ema_latency(health.avg_latency_ms, outcome.latency_ms)
            self.session.commit()
            return SourceFetchResult(
                source_name=source.name,
                source_type=source.source_type,
                status="ok",
                fetched_count=len(items),
                inserted_count=inserted_count,
                error=None,
                latency_ms=outcome.latency_ms,
                inserted_items=inserted_items,
            )
        except Exception as exc:
            # 兜底范围刻意保持宽泛:调用方 (service.refresh_all) 用一个不带
            # try/except 的 `for outcome in outcomes:` 循环串行调用本方法 —— 一旦
            # 这里让异常逃逸,会中断同批后续 source 的落库(已抓取但未及处理的
            # source 结果全部丢失)。批内异常主要来自 SQLAlchemy 写入
            # (session.add/flush/commit 等 SQLAlchemyError 及其子类),类型面
            # 较宽,无法安全穷举收窄,因此维持 Exception 兜底,仅补充带 source
            # 上下文的日志(此前完全没有日志,属于"吞错不留痕"）。
            self.session.rollback()
            logger.exception(
                "news persist failed: source=%s type=%s url=%s latency_ms=%s",
                source.name,
                source.source_type,
                source.url,
                outcome.latency_ms,
            )
            return self.record_failure(
                source,
                error=str(exc),
                latency_ms=outcome.latency_ms,
                status="parse_error",
                http_status=outcome.http_status,
            )

    def record_failure(
        self,
        source: SourceDefinition,
        *,
        error: str,
        latency_ms: float,
        status: str = "http_error",
        http_status: int | None = None,
    ) -> SourceFetchResult:
        health = self.source_health_repository.get_or_create(
            source_name=source.name,
            source_type=source.source_type,
            market=source.market,
        )
        health.last_failure_at = _utc_now()
        health.total_failures += 1
        health.consecutive_failures += 1
        health.consecutive_empty_batches = 0
        health.last_status = status
        health.last_error = error
        health.last_http_status = http_status
        health.last_fetched_count = 0
        health.last_inserted_count = 0
        self.session.commit()
        return SourceFetchResult(
            source_name=source.name,
            source_type=source.source_type,
            status=status,
            fetched_count=0,
            inserted_count=0,
            error=error,
            latency_ms=latency_ms,
        )

    def persist_item(self, source: SourceDefinition, item: SourceItem) -> NewsItem | None:
        canonical_url = item.canonical_url
        url_hash = sha256(canonical_url.encode("utf-8")).hexdigest()
        existing = self.session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
        if existing is not None:
            self.update_existing_item(existing, item, source=source)
            # 更新可能回填 published_at / 标题元数据,同步进批内查重索引。
            self.duplicate_gate.register(existing)
            return None

        duplicate = self.duplicate_gate.find_duplicate(item)
        if duplicate is not None:
            self.update_existing_item(duplicate, item, source=source)
            self.duplicate_gate.register(duplicate)
            return None

        if not passes_ingest_relevance_gate(
            title=item.title,
            summary=item.summary,
            body_excerpt=item.content_text,
            source_name=source.name,
        ):
            logger.info(
                "skip low-relevance ingest: source=%s title=%s",
                source.name,
                item.title[:120],
            )
            return None

        fetched_at = _utc_now()
        news_item = NewsItem(
            source_name=source.name,
            source_url=source.url,
            title=item.title[:500],
            summary=item.summary,
            canonical_url=canonical_url,
            url_hash=url_hash,
            market=source.market,
            language=source.language,
            sentiment_label=None,
            sentiment_score=None,
            published_at=item.published_at,
            fetched_at=fetched_at,
            effective_at=item.published_at or fetched_at,
            ingest_status="ingested",
        )
        self.session.add(news_item)
        self.session.flush()
        # 新行加入批内查重索引,供同批后续 item 判重。
        self.duplicate_gate.register(news_item)
        extract_status = item.extract_status or ("success" if item.content_text else None)
        if extract_status:
            self.session.add(
                ArticleContent(
                    news_id=news_item.id,
                    content_text=item.content_text,
                    content_html=item.content_html,
                    extract_status=extract_status,
                    extract_error=item.extract_error,
                    extracted_at=_utc_now(),
                )
            )
        return news_item

    def update_existing_item(
        self,
        news_item: NewsItem,
        item: SourceItem,
        *,
        source: SourceDefinition | None = None,
    ) -> None:
        self.session.flush()
        if source is not None and _should_promote_source_metadata(news_item, source):
            news_item.source_name = source.name
            news_item.source_url = source.url
            news_item.market = source.market
            news_item.language = source.language
        if item.summary and (
            not news_item.summary
            or news_item.summary.startswith("模型 文本 ")
        ):
            news_item.summary = item.summary
        if item.published_at and news_item.published_at is None:
            news_item.published_at = item.published_at
            news_item.effective_at = news_item.published_at or news_item.fetched_at

        extract_status = item.extract_status or ("success" if item.content_text else None)
        if not extract_status:
            return

        article = self.session.scalar(select(ArticleContent).where(ArticleContent.news_id == news_item.id))
        if article is None:
            self.session.add(
                ArticleContent(
                    news_id=news_item.id,
                    content_text=item.content_text,
                    content_html=item.content_html,
                    extract_status=extract_status,
                    extract_error=item.extract_error,
                    extracted_at=_utc_now(),
                )
            )
            return

        if extract_status == "success" and (
            article.extract_status != "success"
            or (article.content_text or "").startswith("模型 文本 ")
        ):
            article.content_text = item.content_text
            article.content_html = item.content_html
            article.extract_status = "success"
            article.extract_error = None
            article.extracted_at = _utc_now()
            return

        if article.extract_status == "pending":
            article.extract_status = extract_status
            article.extract_error = item.extract_error
            article.content_text = item.content_text
            article.content_html = item.content_html
            article.extracted_at = _utc_now()
