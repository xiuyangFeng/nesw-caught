from pydantic import BaseModel, Field

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
    editorial_score: float | None = None


class NewsListPageView(BaseModel):
    items: list[NewsItemSummary]
    next_cursor: str | None = None


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


class NewsFeedEventCardView(BaseModel):
    event_key: str
    event_title: str
    event_summary: str | None = None
    event_type: str
    market: str
    sentiment_label: str
    importance_score: float
    last_seen_at: UTCDateTime | None = None
    primary_symbol: str | None = None
    related_symbols: list[str]
    watchlist_hits: list[str] = Field(default_factory=list)
    source_count: int
    news_count: int
    news_items: list[NewsItemSummary]


class NewsEventDetailView(NewsFeedEventCardView):
    pass


class NewsFeedTopicView(BaseModel):
    id: int
    topic_title: str
    topic_summary: str | None = None
    keywords: list[str]
    market: str
    sentiment_label: str
    importance_score: float
    news_count: int
    last_seen_at: UTCDateTime
    related_symbols: list[str]


class NewsFeedLayoutView(BaseModel):
    events: list[NewsFeedEventCardView]
    topics: list[NewsFeedTopicView]
    stream: list[NewsItemSummary]
