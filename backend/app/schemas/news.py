from datetime import datetime

from pydantic import BaseModel


class NewsItemSummary(BaseModel):
    id: int
    title: str
    summary: str | None = None
    source_name: str
    canonical_url: str | None = None
    market: str
    sentiment_label: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime


class NewsMentionView(BaseModel):
    symbol: str
    market: str
    mention_type: str
    confidence: float


class NewsTopicRefView(BaseModel):
    id: int
    topic_title: str
    importance_score: float
    last_seen_at: datetime | None = None


class NewsArticleView(BaseModel):
    content_text: str | None = None
    extract_status: str
    extract_error: str | None = None
    extracted_at: datetime | None = None


class NewsDetailView(NewsItemSummary):
    sentiment_score: float | None = None
    article: NewsArticleView | None = None
    mentions: list[NewsMentionView]
    topic: NewsTopicRefView | None = None
