from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.news_signal_repository import NewsSignalRepository
from app.services.ingestion.article_crawler import (
    DEFAULT_PARSE_CONCURRENCY,
    crawl_and_extract_article,
)
from app.services.news_signal_classifier import ClassificationResult, NewsSignalClassifier
from app.services.quant.mention_backfill import match_a_share_mentions, persist_rule_mentions

logger = logging.getLogger(__name__)

# 阶段 2 分类(可能触发 LLM 网络调用)的并发上限:取小值,避免打爆下游配额。
# 运行时取值来自 settings.news_classify_max_workers,这里是兜底默认值。
MAX_CLASSIFY_WORKERS = 4
# 阶段 1 正文抓取的并发上限兜底默认值(运行时取 settings.news_crawl_max_workers)。
MAX_CRAWL_WORKERS = 8


def _setting(attr: str, default: int) -> int:
    try:
        return max(int(getattr(get_settings(), attr)), 1)
    except Exception:  # pragma: no cover - 配置不可用是极端情况
        return default

# —— 可观测性:被 `except Exception` 吞掉的失败计数(进程内累计,模块级) ——
# 单条抓取失败不影响整批(既有语义不变,已把结果落为 extract_status="failed"),
# 但吞掉的异常此前完全不可观测;这里只加计数,不改变控制流。
# `BackgroundQueueWorker` 会周期性读取该计数并把增量回写到既有的
# `worker_runtime_status` 表,而不是引入新的外部指标依赖。
_pipeline_metrics_lock = threading.Lock()
_pipeline_error_counts: dict[str, int] = {"crawl_error": 0}


def get_pipeline_error_counts() -> dict[str, int]:
    """返回管线内部累计的(被吞掉的)异常计数快照,供上层 worker 周期性上报。"""
    with _pipeline_metrics_lock:
        return dict(_pipeline_error_counts)


def _incr_pipeline_error(key: str) -> None:
    with _pipeline_metrics_lock:
        _pipeline_error_counts[key] = _pipeline_error_counts.get(key, 0) + 1


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ProcessNewsSignalsSummary:
    news_ids: list[int]
    processed_count: int
    touched_topic_ids: list[int]


def _upsert_article_content(
    session: Session,
    *,
    news_id: int,
    text: str | None,
    status: str,
    err: str | None,
) -> None:
    """按 news_id upsert 正文记录(单一 helper,供短事务/单 Session 两种模式复用)。"""
    existing = session.scalar(select(ArticleContent).where(ArticleContent.news_id == news_id))
    if existing is None:
        session.add(
            ArticleContent(
                news_id=news_id,
                content_text=text,
                content_html=None,
                extract_status=status,
                extract_error=err,
                extracted_at=_utc_now(),
            )
        )
    else:
        existing.content_text = text
        existing.extract_status = status
        existing.extract_error = err
        existing.extracted_at = _utc_now()


class NewsSignalPipelineService:
    def __init__(
        self,
        session: Session,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.repository = NewsSignalRepository(session)
        self.classifier = NewsSignalClassifier(session)

    def _safe_crawl(self, url: str) -> tuple[str | None, str, str | None]:
        try:
            logger.info("Attempting to crawl article body: %s", url)
            content = crawl_and_extract_article(url)
            if content:
                return content, "success", None
            else:
                return None, "failed", "Empty content extracted"
        except Exception as exc:
            logger.warning("Failed to automatically crawl article body for %s: %s", url, exc)
            # 可恢复失败:不抛出,单条不影响整批;已经把结果落为 extract_status="failed"
            # (调用方 _upsert_article_content 会写入),这里只补上计数使其可观测。
            _incr_pipeline_error("crawl_error")
            return None, "failed", str(exc)

    def _ensure_articles(self, news_ids: list[int]) -> int:
        """阶段 1：对未爬取正文的新闻并行同步爬取，然后一次性批量落库。

        关键不变量:全部网络 I/O(爬正文)在线程池里跑完之后才开始写事务,写事务
        内没有任何网络调用。此前是"逐条一个独立 Session + commit",50 条就是 50 次
        写事务(50 次锁获取 + fsync);改成一次事务批量提交,仍然满足上述不变量。
        """
        items = self.repository.list_news(news_ids)
        have = self.repository.get_article_map(news_ids)

        to_crawl = []
        for item in items:
            art = have.get(item.id)
            if (art and art.extract_status == "success") or not item.canonical_url:
                continue
            to_crawl.append(item)

        if not to_crawl:
            return 0

        # 网络并发（下面的线程池）与解析并发（article_crawler 里的模块级信号量）是
        # 两个独立的旋钮：网络是 I/O 等待，高并发有收益；解析是纯 CPU 且持有 GIL，
        # 必须限流，否则会饿死 uvicorn 事件循环。这里只读取解析配额用于日志观测，
        # 真正的限流发生在 crawl_and_extract_article 内部。
        max_workers = min(len(to_crawl), _setting("news_crawl_max_workers", MAX_CRAWL_WORKERS))
        parse_slots = _setting("news_crawl_parse_concurrency", DEFAULT_PARSE_CONCURRENCY)

        def task_fn(news_item):
            text, status, err = self._safe_crawl(news_item.canonical_url)
            return news_item.id, text, status, err

        crawl_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-crawl") as executor:
            results = list(executor.map(task_fn, to_crawl))
        crawl_ms = (time.perf_counter() - crawl_started) * 1000

        # —— 网络 I/O 到此全部结束,下面才进入写事务 ——
        persist_started = time.perf_counter()
        if self.session_factory is not None:
            # 独立 Session + 单次批量提交(此前是逐条一个事务)。
            with self.session_factory() as s:
                for news_id, text, status, err in results:
                    _upsert_article_content(s, news_id=news_id, text=text, status=status, err=err)
                s.commit()
        else:
            # 单 Session 模式下 (例如测试环境)，直接使用主 session 写入并 flush
            for news_id, text, status, err in results:
                _upsert_article_content(self.session, news_id=news_id, text=text, status=status, err=err)
            self.session.flush()
        logger.info(
            "pipeline stage1 crawl done: candidates=%s crawled=%s crawl_ms=%.1f persist_ms=%.1f "
            "workers=%s parse_slots=%s",
            len(items),
            len(results),
            crawl_ms,
            (time.perf_counter() - persist_started) * 1000,
            max_workers,
            parse_slots,
        )
        return len(results)

    def process_news_ids(self, news_ids: list[int]) -> ProcessNewsSignalsSummary:
        if not news_ids:
            return ProcessNewsSignalsSummary(news_ids=[], processed_count=0, touched_topic_ids=[])

        total_started = time.perf_counter()

        # —— 阶段 1: 正文补全 ——
        stage_started = time.perf_counter()
        crawled = self._ensure_articles(news_ids)
        ensure_ms = (time.perf_counter() - stage_started) * 1000

        # —— 阶段 2a: 分类(可能含 LLM 网络 I/O),纯内存完成,不触碰写事务 ——
        stage_started = time.perf_counter()
        news_items = self.repository.list_news(news_ids)
        article_map = self.repository.get_article_map(news_ids)

        classify_inputs: list[tuple[int, str, str | None, str | None]] = []
        for item in news_items:
            article = article_map.get(item.id)
            body = article.content_text if article and article.content_text else None
            classify_inputs.append((item.id, item.title, item.summary, body))

        results = self._classify_batch(classify_inputs)
        classify_ms = (time.perf_counter() - stage_started) * 1000

        # —— 阶段 2b: 全部网络 I/O 结束后,统一在主 Session 短事务内落库 ——
        stage_started = time.perf_counter()
        touched_topic_ids: set[int] = set()
        processed_news_ids: list[int] = []

        for item in news_items:
            article = article_map.get(item.id)
            body = article.content_text if article and article.content_text else None
            self._apply_result(item, results[item.id], touched_topic_ids, body=body)
            processed_news_ids.append(item.id)

        self.repository.refresh_topic_stats(touched_topic_ids)
        apply_ms = (time.perf_counter() - stage_started) * 1000
        logger.info(
            "pipeline process_news_ids done: requested=%s processed=%s crawled=%s topics=%s "
            "ensure_articles_ms=%.1f classify_ms=%.1f apply_ms=%.1f total_ms=%.1f",
            len(news_ids),
            len(processed_news_ids),
            crawled,
            len(touched_topic_ids),
            ensure_ms,
            classify_ms,
            apply_ms,
            (time.perf_counter() - total_started) * 1000,
        )
        return ProcessNewsSignalsSummary(
            news_ids=processed_news_ids,
            processed_count=len(processed_news_ids),
            touched_topic_ids=sorted(touched_topic_ids),
        )

    def _classify_batch(
        self, inputs: list[tuple[int, str, str | None, str | None]]
    ) -> dict[int, ClassificationResult]:
        """对一批新闻做分类。

        有 session_factory 时用小线程池并行(每线程独立 Session + Classifier,
        LLM provider/repository 不跨线程共享);否则退回主 Session 串行,
        保持测试等单 Session 场景的原有行为。
        """
        if not inputs:
            return {}

        if self.session_factory is None or len(inputs) == 1:
            return {
                news_id: self.classifier.classify(title=title, summary=summary, body=body)
                for news_id, title, summary, body in inputs
            }

        def task_fn(payload: tuple[int, str, str | None, str | None]):
            news_id, title, summary, body = payload
            with self.session_factory() as s:
                classifier = NewsSignalClassifier(s)
                return news_id, classifier.classify(title=title, summary=summary, body=body)

        max_workers = min(len(inputs), _setting("news_classify_max_workers", MAX_CLASSIFY_WORKERS))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-classify") as pool:
            return dict(pool.map(task_fn, inputs))

    def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
        return self.repository.list_pending_news_ids(limit=limit)

    def _apply_result(
        self,
        item: NewsItem,
        result: ClassificationResult,
        touched_topic_ids: set[int],
        body: str | None = None,
    ) -> None:
        """将分类结果落库(纯数据库写,无网络 I/O)。"""
        topic = self.repository.find_topic(topic_key=result.topic_key, keywords=result.keywords)
        if topic is None:
            topic = self.repository.create_topic(
                topic_key=result.topic_key,
                topic_title=result.topic_title_hint or result.topic_key.title(),
                topic_summary=result.topic_summary_hint or result.summary,
                keywords=result.keywords,
                last_seen_at=item.published_at or item.fetched_at,
            )
        else:
            if not topic.topic_summary and result.summary:
                topic.topic_summary = result.summary
            if not topic.keywords and result.keywords:
                topic.keywords = ",".join(result.keywords)
            topic.last_seen_at = max(filter(None, [topic.last_seen_at, item.published_at, item.fetched_at]))

        if result.classifier_type == "hybrid":
            topic.llm_refined_at = _utc_now()

        item.sentiment_label = result.sentiment_label
        item.sentiment_score = result.sentiment_score
        item.signal_status = "processed"
        item.signal_error = result.llm_error
        item.signal_updated_at = _utc_now()
        if result.takeaway and not item.ai_takeaway:
            item.ai_takeaway = result.takeaway

        self.repository.ensure_link(topic_id=topic.id, news_id=item.id)
        self.repository.upsert_signal_result(
            news_id=item.id,
            classifier_type=result.classifier_type,
            signal_confidence=result.signal_confidence,
            topic_key=result.topic_key,
            keywords=result.keywords,
            summary=result.summary,
            payload={
                "sentiment_label": result.sentiment_label,
                "sentiment_score": result.sentiment_score,
                "topic_title_hint": result.topic_title_hint,
                "llm_error": result.llm_error,
            },
        )
        touched_topic_ids.add(topic.id)
        persist_rule_mentions(
            self.session,
            item.id,
            match_a_share_mentions(item.title, item.summary, body),
        )
