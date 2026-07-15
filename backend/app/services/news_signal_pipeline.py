from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.news_signal_repository import NewsSignalRepository
from app.services.ingestion.article_crawler import crawl_and_extract_article
from app.services.news_signal_classifier import ClassificationResult, NewsSignalClassifier

logger = logging.getLogger(__name__)

# 阶段 2 分类(可能触发 LLM 网络调用)的并发上限:取小值,避免打爆下游配额。
MAX_CLASSIFY_WORKERS = 4


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
            return None, "failed", str(exc)

    def _ensure_articles(self, news_ids: list[int]) -> None:
        """阶段 1：对未爬取正文的新闻并行同步爬取，并以独立短事务逐条落库。"""
        items = self.repository.list_news(news_ids)
        have = self.repository.get_article_map(news_ids)

        to_crawl = []
        for item in items:
            art = have.get(item.id)
            if (art and art.extract_status == "success") or not item.canonical_url:
                continue
            to_crawl.append(item)

        if not to_crawl:
            return

        max_workers = min(len(to_crawl), 8)

        def task_fn(news_item):
            text, status, err = self._safe_crawl(news_item.canonical_url)
            return news_item.id, text, status, err

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(task_fn, to_crawl))

        for news_id, text, status, err in results:
            if self.session_factory is not None:
                # 只有在有 session_factory 时，才使用独立新 Session 逐条提交
                with self.session_factory() as s:
                    _upsert_article_content(s, news_id=news_id, text=text, status=status, err=err)
                    s.commit()
            else:
                # 单 Session 模式下 (例如测试环境)，直接使用主 session 写入并 flush
                _upsert_article_content(self.session, news_id=news_id, text=text, status=status, err=err)
                self.session.flush()

    def process_news_ids(self, news_ids: list[int]) -> ProcessNewsSignalsSummary:
        if not news_ids:
            return ProcessNewsSignalsSummary(news_ids=[], processed_count=0, touched_topic_ids=[])

        # —— 阶段 1: 正文补全 ——
        self._ensure_articles(news_ids)

        # —— 阶段 2a: 分类(可能含 LLM 网络 I/O),纯内存完成,不触碰写事务 ——
        news_items = self.repository.list_news(news_ids)
        article_map = self.repository.get_article_map(news_ids)

        classify_inputs: list[tuple[int, str, str | None, str | None]] = []
        for item in news_items:
            article = article_map.get(item.id)
            body = article.content_text if article and article.content_text else None
            classify_inputs.append((item.id, item.title, item.summary, body))

        results = self._classify_batch(classify_inputs)

        # —— 阶段 2b: 全部网络 I/O 结束后,统一在主 Session 短事务内落库 ——
        touched_topic_ids: set[int] = set()
        processed_news_ids: list[int] = []

        for item in news_items:
            self._apply_result(item, results[item.id], touched_topic_ids)
            processed_news_ids.append(item.id)

        self.repository.refresh_topic_stats(touched_topic_ids)
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

        max_workers = min(len(inputs), MAX_CLASSIFY_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-classify") as pool:
            return dict(pool.map(task_fn, inputs))

    def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
        return self.repository.list_pending_news_ids(limit=limit)

    def _apply_result(
        self,
        item: NewsItem,
        result: ClassificationResult,
        touched_topic_ids: set[int],
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
