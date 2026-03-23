from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.news_item import NewsItem
from app.repositories.news_signal_repository import NewsSignalRepository
from app.services.news_signal_classifier import NewsSignalClassifier


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProcessNewsSignalsSummary:
    news_ids: list[int]
    processed_count: int
    touched_topic_ids: list[int]


class NewsSignalPipelineService:
    def __init__(self, session) -> None:
        self.session = session
        self.repository = NewsSignalRepository(session)
        self.classifier = NewsSignalClassifier(session)

    def process_news_ids(self, news_ids: list[int]) -> ProcessNewsSignalsSummary:
        if not news_ids:
            return ProcessNewsSignalsSummary(news_ids=[], processed_count=0, touched_topic_ids=[])

        news_items = self.repository.list_news(news_ids)
        article_map = self.repository.get_article_map(news_ids)
        touched_topic_ids: set[int] = set()
        processed_news_ids: list[int] = []

        for item in news_items:
            self._process_item(item, article_map.get(item.id), touched_topic_ids)
            processed_news_ids.append(item.id)

        self.repository.refresh_topic_stats(touched_topic_ids)
        return ProcessNewsSignalsSummary(
            news_ids=processed_news_ids,
            processed_count=len(processed_news_ids),
            touched_topic_ids=sorted(touched_topic_ids),
        )

    def list_pending_news_ids(self, *, limit: int = 50) -> list[int]:
        return self.repository.list_pending_news_ids(limit=limit)

    def _process_item(self, item: NewsItem, article, touched_topic_ids: set[int]) -> None:
        result = self.classifier.classify(
            title=item.title,
            summary=item.summary,
            body=(article.content_text if article and article.content_text else None),
        )
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
