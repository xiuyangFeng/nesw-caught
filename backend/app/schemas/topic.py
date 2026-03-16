from datetime import datetime

from pydantic import BaseModel

from app.schemas.news import NewsItemSummary


class TopicItemView(BaseModel):
    id: int
    topic_title: str
    topic_summary: str | None = None
    keywords: list[str]
    market: str
    sentiment_label: str
    importance_score: float
    news_count: int
    last_seen_at: datetime
    related_symbols: list[str]


class TopicDetailView(TopicItemView):
    sources: list[NewsItemSummary]
