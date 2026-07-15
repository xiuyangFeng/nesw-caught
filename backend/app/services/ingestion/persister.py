from __future__ import annotations

import logging
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.dedup_gate import DuplicateGate
from app.services.ingestion.parser import _parse_minimax_detail_html
from app.services.ingestion.sources import _should_promote_source_metadata
from app.services.ingestion.types import (
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
    SourceItem,
)
from app.services.ingestion.utils import _ema_latency, _utc_now

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

        if outcome.error is not None:
            return self.record_failure(source, error=outcome.error, latency_ms=outcome.latency_ms)

        # 保存最新的 ETag / Last-Modified 缓存标头
        health.last_etag = outcome.etag
        health.last_modified = outcome.last_modified

        if outcome.is_not_modified:
            health.last_success_at = _utc_now()
            health.consecutive_failures = 0
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
            if source.name == "MiniMax News":
                from app.services import news_ingestion
                # 详情页补全需要读库判断是否已完整,因此放在串行阶段执行。
                with news_ingestion.HttpClientFactory().create() as client:
                    items = [self.hydrate_minimax_detail_item(client, source, item) for item in items]

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
            # (session.add/flush/commit 等 SQLAlchemyError 及其子类),但 MiniMax
            # 分支还会经由 hydrate_minimax_detail_item 触达 httpx 网络层,类型面
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
            return self.record_failure(source, error=str(exc), latency_ms=outcome.latency_ms)

    def record_failure(self, source: SourceDefinition, *, error: str, latency_ms: float) -> SourceFetchResult:
        health = self.source_health_repository.get_or_create(
            source_name=source.name,
            source_type=source.source_type,
            market=source.market,
        )
        health.last_failure_at = _utc_now()
        health.total_failures += 1
        health.consecutive_failures += 1
        self.session.commit()
        return SourceFetchResult(
            source_name=source.name,
            source_type=source.source_type,
            status="error",
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
            fetched_at=_utc_now(),
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

    def hydrate_minimax_detail_item(
        self,
        client,
        source: SourceDefinition,
        item: SourceItem,
    ) -> SourceItem:
        canonical_url = item.canonical_url
        url_hash = sha256(canonical_url.encode("utf-8")).hexdigest()
        existing = self.session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
        if existing is not None:
            article = self.session.scalar(select(ArticleContent).where(ArticleContent.news_id == existing.id))
            article_looks_complete = (
                article is not None
                and article.extract_status == "success"
                and not (article.content_text or "").startswith("模型 文本 ")
            )
            if existing.published_at is not None and article_looks_complete:
                return item

        try:
            response = client.get(canonical_url)
            response.raise_for_status()
            detail_item = _parse_minimax_detail_html(
                response.text,
                source,
                canonical_url=canonical_url,
                fallback_title=item.title,
            )
            if existing is not None and existing.summary and not detail_item.summary:
                detail_item = SourceItem(
                    title=detail_item.title,
                    canonical_url=detail_item.canonical_url,
                    summary=existing.summary,
                    content_text=detail_item.content_text,
                    published_at=detail_item.published_at,
                    content_html=detail_item.content_html,
                    extract_status=detail_item.extract_status,
                    extract_error=detail_item.extract_error,
                )
            return detail_item
        except Exception as exc:
            # 兜底范围刻意保持宽泛:失败时优雅降级为回退 item(而非向上抛出),
            # 让调用方 persist_outcome 把该 source 的其余 item 正常落库,不因单条
            # MiniMax 详情页失败拖垮整批。可能的异常包括 httpx 网络层
            # (含不属于 httpx.HTTPError 体系的 httpx.InvalidURL/StreamError 等)
            # 与 _parse_minimax_detail_html 显式抛出的 ValueError,类型面无法安全
            # 穷举收窄,因此维持 Exception 兜底,仅补充带 URL 上下文的日志
            # (此前完全没有日志)。
            logger.warning(
                "minimax detail hydration failed: source=%s url=%s error=%s",
                source.name,
                canonical_url,
                exc,
                exc_info=True,
            )
            if existing is not None and existing.published_at is not None:
                return item
            return SourceItem(
                title=item.title,
                canonical_url=item.canonical_url,
                summary=item.summary,
                content_text=None,
                content_html=None,
                published_at=item.published_at,
                extract_status="failed",
                extract_error=str(exc),
            )
