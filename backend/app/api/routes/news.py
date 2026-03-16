from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleView, NewsDetailView, NewsItemSummary, NewsMentionView, NewsTopicRefView

router = APIRouter()


@router.get("", response_model=list[NewsItemSummary])
def list_news(session: Session = Depends(get_db_session)) -> list[NewsItemSummary]:
    repository = NewsRepository(session)
    return [NewsItemSummary.model_validate(item, from_attributes=True) for item in repository.list_recent(limit=200)]


@router.get("/{news_id}", response_model=NewsDetailView)
def get_news_detail(news_id: int, session: Session = Depends(get_db_session)) -> NewsDetailView:
    repository = NewsRepository(session)
    item = repository.get_by_id(news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="news not found")

    article = repository.get_article(news_id)
    mentions = repository.list_mentions(news_id)
    topic = repository.get_topic_for_news(news_id)

    return NewsDetailView(
        **NewsItemSummary.model_validate(item, from_attributes=True).model_dump(),
        sentiment_score=item.sentiment_score,
        article=(
            NewsArticleView(
                content_text=article.content_text,
                extract_status=article.extract_status,
                extract_error=article.extract_error,
                extracted_at=article.extracted_at,
            )
            if article
            else None
        ),
        mentions=[
            NewsMentionView(
                symbol=mention.symbol,
                market=mention.market,
                mention_type=mention.mention_type,
                confidence=mention.confidence,
            )
            for mention in mentions
        ],
        topic=(
            NewsTopicRefView(
                id=topic.id,
                topic_title=topic.topic_title,
                importance_score=topic.importance_score or 0.0,
                last_seen_at=topic.last_seen_at,
            )
            if topic
            else None
        ),
    )
