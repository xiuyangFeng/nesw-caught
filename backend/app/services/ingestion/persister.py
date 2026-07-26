from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.dedup_gate import (
    TITLE_SIGNATURE_MAX_LENGTH,
    DuplicateGate,
    normalize_url_for_hash,
)
from app.services.ingestion.sources import _should_promote_source_metadata
from app.services.ingestion.types import (
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
    SourceItem,
)
from app.services.ingestion.utils import _ema_latency, _utc_now
from app.services.news_priority import evaluate_ingest_relevance_gate

logger = logging.getLogger(__name__)


@dataclass
class BatchDropStats:
    """一批 items 的丢弃归因(P0-3 可观测性)。

    此前 `fetched_count - inserted_count` 把"重复"和"闸门拒绝"两种语义混在一起，
    运维面板上"抓了 20 入 0"完全无法归因。这里按原因分类计数。

    限制说明：`SourceFetchResult` 定义在 `ingestion/types.py`（WS-6 归属，本次不改），
    无法新增 duplicate_count / filtered_count 字段，因此计数以
    (a) 结构化 INFO 日志 与 (b) `ItemPersister.last_batch_stats` 属性
    两种方式暴露，暂不进 DB。后续 types.py 可扩展时直接搬进 SourceFetchResult。
    """

    fetched: int = 0
    inserted: int = 0
    url_duplicate: int = 0  # url_hash 精确命中
    near_duplicate: int = 0  # 签名/SimHash 近重复命中
    filtered: int = 0  # 相关性闸门拒绝
    filter_reasons: Counter[str] = field(default_factory=Counter)

    @property
    def duplicate(self) -> int:
        return self.url_duplicate + self.near_duplicate

    def as_log_fields(self) -> str:
        top_reasons = ",".join(f"{reason}={count}" for reason, count in self.filter_reasons.most_common(5))
        return (
            f"fetched={self.fetched} inserted={self.inserted} "
            f"duplicate={self.duplicate}(url={self.url_duplicate},near={self.near_duplicate}) "
            f"filtered={self.filtered} filter_reasons=[{top_reasons}]"
        )


class ItemPersister:
    def __init__(self, session: Session, source_health_repository: SourceHealthRepository) -> None:
        self.session = session
        self.source_health_repository = source_health_repository
        self.duplicate_gate = DuplicateGate(session)
        # 最近一批的丢弃归因,供调用方/测试读取(见 BatchDropStats 的限制说明)。
        self.last_batch_stats = BatchDropStats()
        self._active_stats: BatchDropStats | None = None

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
            # 丢弃归因通过实例状态传递而非 persist_item 参数:persist_item 是公开
            # 入口(service._persist_item / 测试直接调用),签名保持不变。
            stats = BatchDropStats(fetched=len(items))
            self.last_batch_stats = stats
            self._active_stats = stats
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
                self._active_stats = None
                self.duplicate_gate.invalidate()
            stats.inserted = inserted_count

            health.last_success_at = _utc_now()
            health.consecutive_failures = 0
            health.consecutive_empty_batches = 0
            health.last_status = "ok"
            health.last_error = None
            health.last_fetched_count = len(items)
            health.last_inserted_count = inserted_count
            health.avg_latency_ms = _ema_latency(health.avg_latency_ms, outcome.latency_ms)
            self.session.commit()
            # 结构化丢弃归因:让"抓了 20 入 0"能直接在日志里区分是重复还是被闸门拒。
            logger.info(
                "news source persisted: source=%s type=%s %s latency_ms=%s",
                source.name,
                source.source_type,
                stats.as_log_fields(),
                outcome.latency_ms,
            )
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
        logger.warning(
            "news source fetch failed, recorded and moving to next cycle: source=%s type=%s status=%s "
            "http_status=%s latency_ms=%s error=%s",
            source.name,
            source.source_type,
            status,
            http_status,
            latency_ms,
            error,
        )
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
        stats = self._active_stats
        canonical_url = item.canonical_url
        # P1-2：url_hash 基于归一化后的 URL 计算(剥 utm_* 等跟踪参数、去 fragment、
        # 参数排序)，让"同一文章带不同 utm"落在同一个 hash 上;
        # 入库的 canonical_url 仍保留原始可点击链接,不做改写。
        url_hash = sha256(normalize_url_for_hash(canonical_url).encode("utf-8")).hexdigest()
        existing = self.session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
        if existing is not None:
            self.update_existing_item(existing, item, source=source, url_hash=url_hash)
            # 更新可能回填 published_at / 标题元数据,同步进批内查重索引。
            self.duplicate_gate.register(existing)
            if stats is not None:
                stats.url_duplicate += 1
            return None

        duplicate = self.duplicate_gate.find_duplicate(item)
        if duplicate is not None:
            self.update_existing_item(duplicate, item, source=source, url_hash=url_hash)
            self.duplicate_gate.register(duplicate)
            if stats is not None:
                stats.near_duplicate += 1
            return None

        decision = evaluate_ingest_relevance_gate(
            title=item.title,
            summary=item.summary,
            body_excerpt=item.content_text,
            source_name=source.name,
            has_stock_refs=item.has_stock_refs,
        )
        if not decision.passed:
            if stats is not None:
                stats.filtered += 1
                stats.filter_reasons[decision.reason] += 1
            # 带上拒绝原因(哪条规则拒的),否则闸门无法回放、无法调参。
            logger.info(
                "skip low-relevance ingest: source=%s reason=%s title=%s",
                source.name,
                decision.reason,
                item.title[:120],
            )
            return None

        fetched_at = _utc_now()
        news_item = NewsItem(
            source_name=source.name,
            source_url=source.url,
            title=item.title[:TITLE_SIGNATURE_MAX_LENGTH],
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
        url_hash: str | None = None,
    ) -> None:
        self.session.flush()
        if source is not None and _should_promote_source_metadata(news_item, source):
            # P2 语义修正：跨源命中同一事件时，元数据整体切换到更高等级的来源，
            # 【canonical_url 与 source_name 必须一起换】。
            # 此前只换 source_name/source_url/market/language 而保留旧的 canonical_url，
            # 结果是"source_name 显示 SEC Press Releases，点进去却是 Yahoo 转载"。
            # 现在的自洽语义是：一行新闻的 source_* 与 canonical_url 始终描述同一个来源。
            # 只在【确实换了来源】时才动链接：同源重复(如同一 feed 内的改写标题)
            # 保留首次入库的链接，避免把 canonical_url 在同源条目间来回摆动。
            if news_item.source_name != source.name:
                self._promote_canonical_url(news_item, item, url_hash=url_hash)
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

    def _promote_canonical_url(
        self,
        news_item: NewsItem,
        item: SourceItem,
        *,
        url_hash: str | None,
    ) -> None:
        """把 canonical_url / url_hash 一并切换到更高等级来源的链接。

        canonical_url 与 url_hash 都带 unique 约束：若目标 hash 已被【另一行】占用
        （同一篇文章在库里另有独立记录），放弃切换而不是抛 IntegrityError 断掉整批。
        """
        incoming_url = item.canonical_url
        if not incoming_url or incoming_url == news_item.canonical_url:
            return
        incoming_hash = url_hash or sha256(
            normalize_url_for_hash(incoming_url).encode("utf-8")
        ).hexdigest()
        if incoming_hash == news_item.url_hash:
            # 归一化后是同一篇文章，只是原始链接带了不同的跟踪参数：hash 不变，无冲突风险。
            news_item.canonical_url = incoming_url
            return
        conflict = self.session.scalar(
            select(NewsItem.id).where(
                NewsItem.url_hash == incoming_hash,
                NewsItem.id != news_item.id,
            )
        )
        if conflict is not None:
            logger.info(
                "skip canonical_url promotion due to unique conflict: news_id=%s incoming=%s",
                news_item.id,
                incoming_url[:160],
            )
            return
        news_item.canonical_url = incoming_url
        news_item.url_hash = incoming_hash
