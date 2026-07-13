from __future__ import annotations

import json
from datetime import datetime
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_signal_result import NewsSignalResult
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink


class NewsSignalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_news(self, news_ids: list[int]) -> list[NewsItem]:
        stmt = select(NewsItem).where(NewsItem.id.in_(news_ids)).order_by(NewsItem.id.asc())
        return list(self.session.scalars(stmt))

    def list_pending_news_ids(self, *, limit: int) -> list[int]:
        stmt = (
            select(NewsItem.id)
            .where(NewsItem.signal_status.is_(None))
            .order_by(NewsItem.published_at.is_(None).asc(), NewsItem.published_at.desc(), NewsItem.fetched_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_article_map(self, news_ids: list[int]) -> dict[int, ArticleContent]:
        stmt = select(ArticleContent).where(ArticleContent.news_id.in_(news_ids))
        return {item.news_id: item for item in self.session.scalars(stmt)}

    def list_directional_signal_news(self, *, market: str | None, since: datetime) -> list[NewsItem]:
        """回测候选：窗口内、带方向情绪（positive/negative）的新闻（只读）。"""
        stmt = (
            select(NewsItem)
            .where(
                NewsItem.published_at.is_not(None),
                NewsItem.published_at >= since,
                NewsItem.sentiment_label.in_(["positive", "negative"]),
            )
            .order_by(NewsItem.published_at.asc(), NewsItem.id.asc())
        )
        if market:
            stmt = stmt.where(NewsItem.market == market)
        return list(self.session.scalars(stmt))

    def get_signal_result_map(self, news_ids: list[int]) -> dict[int, NewsSignalResult]:
        """按 news_id 取信号结果（含 signal_confidence，用于 importance 分桶）。"""
        if not news_ids:
            return {}
        stmt = select(NewsSignalResult).where(NewsSignalResult.news_id.in_(news_ids))
        return {item.news_id: item for item in self.session.scalars(stmt)}

    def find_topic(self, *, topic_key: str, keywords: list[str]) -> TopicCluster | None:
        exact_stmt = select(TopicCluster).where(TopicCluster.topic_key == topic_key)
        exact = self.session.scalar(exact_stmt)
        if exact is not None:
            return exact

        if not keywords:
            return None

        for topic in self.session.scalars(select(TopicCluster).order_by(TopicCluster.id.asc())):
            existing_keywords = {item.strip().lower() for item in (topic.keywords or "").split(",") if item.strip()}
            if not existing_keywords:
                continue
            overlap = len(existing_keywords.intersection(keywords))
            if overlap >= min(2, len(keywords)):
                return topic
        return None

    def create_topic(
        self,
        *,
        topic_key: str,
        topic_title: str,
        topic_summary: str | None,
        keywords: list[str],
        last_seen_at,
    ) -> TopicCluster:
        topic = TopicCluster(
            topic_key=topic_key,
            topic_title=topic_title,
            topic_summary=topic_summary,
            keywords=",".join(keywords),
            sentiment_score=0.0,
            importance_score=0.0,
            cluster_version=1,
            last_seen_at=last_seen_at,
        )
        self.session.add(topic)
        self.session.flush()
        return topic

    def ensure_link(self, *, topic_id: int, news_id: int) -> None:
        stmt = select(TopicNewsLink).where(
            TopicNewsLink.topic_cluster_id == topic_id,
            TopicNewsLink.news_id == news_id,
        )
        existing = self.session.scalar(stmt)
        if existing is None:
            self.session.add(TopicNewsLink(topic_cluster_id=topic_id, news_id=news_id))

    def upsert_signal_result(
        self,
        *,
        news_id: int,
        classifier_type: str,
        signal_confidence: float | None,
        topic_key: str,
        keywords: list[str],
        summary: str | None,
        payload: dict[str, object] | None,
    ) -> None:
        stmt = select(NewsSignalResult).where(NewsSignalResult.news_id == news_id)
        item = self.session.scalar(stmt)
        if item is None:
            item = NewsSignalResult(news_id=news_id)
            self.session.add(item)
        item.classifier_type = classifier_type
        item.signal_confidence = signal_confidence
        item.topic_key = topic_key
        item.keywords = ",".join(keywords)
        item.summary = summary
        item.payload_json = json.dumps(payload, ensure_ascii=False) if payload else None

    def refresh_topic_stats(self, topic_ids: set[int]) -> None:
        for topic_id in topic_ids:
            topic = self.session.scalar(select(TopicCluster).where(TopicCluster.id == topic_id))
            if topic is None:
                continue

            news_items = list(
                self.session.scalars(
                    select(NewsItem)
                    .join(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
                    .where(TopicNewsLink.topic_cluster_id == topic_id)
                )
            )
            if not news_items:
                continue

            scores = [item.sentiment_score for item in news_items if item.sentiment_score is not None]
            topic.sentiment_score = round(fmean(scores), 4) if scores else 0.0
            topic.last_seen_at = max((item.published_at or item.fetched_at) for item in news_items)
            topic.importance_score = round(
                min(1.0, 0.35 + len(news_items) * 0.15 + min(abs(topic.sentiment_score or 0.0), 0.4)),
                4,
            )
