from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class NewsItemSummary(BaseModel):
    id: int
    title: str
    summary: str | None = None
    source_name: str
    canonical_url: str | None = None
    market: str
    sentiment_label: str | None = None
    published_at: UTCDateTime | None = None
    fetched_at: UTCDateTime


class NewsMentionView(BaseModel):
    symbol: str
    market: str
    mention_type: str
    confidence: float


class NewsTopicRefView(BaseModel):
    id: int
    topic_title: str
    importance_score: float
    last_seen_at: UTCDateTime | None = None


class NewsArticleView(BaseModel):
    content_text: str | None = None
    extract_status: str
    extract_error: str | None = None
    extracted_at: UTCDateTime | None = None


class NewsDetailView(NewsItemSummary):
    sentiment_score: float | None = None
    article: NewsArticleView | None = None
    mentions: list[NewsMentionView]
    topic: NewsTopicRefView | None = None
