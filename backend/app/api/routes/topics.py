from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.topic_repository import TopicRepository
from app.schemas.news import NewsItemSummary
from app.schemas.topic import TopicDetailView, TopicItemView
from app.services.topic_naming import topic_naming_fields

router = APIRouter()


def _keywords(raw_keywords: str | None) -> list[str]:
    if not raw_keywords:
        return []
    return [item.strip() for item in raw_keywords.split(",") if item.strip()]


@router.get("", response_model=list[TopicItemView])
def list_topics(session: Session = Depends(get_db_session)) -> list[TopicItemView]:
    repository = TopicRepository(session)
    topics = repository.list_all()
    response: list[TopicItemView] = []
    for topic in topics:
        news_items = repository.list_news_for_topic(topic.id)
        keywords = _keywords(topic.keywords)
        display_name, alias_zh = topic_naming_fields(
            topic_key=topic.topic_key,
            topic_title=topic.topic_title,
            keywords=keywords,
        )
        response.append(
            TopicItemView(
                id=topic.id,
                topic_title=topic.topic_title,
                display_name=display_name,
                alias_zh=alias_zh,
                topic_summary=topic.topic_summary,
                keywords=keywords,
                market=(news_items[0].market if news_items else "us"),
                sentiment_label="positive" if (topic.sentiment_score or 0) > 0.2 else "negative" if (topic.sentiment_score or 0) < -0.2 else "neutral",
                importance_score=topic.importance_score or 0.0,
                news_count=len(news_items),
                last_seen_at=topic.last_seen_at,
                related_symbols=repository.list_related_symbols(topic.id),
            )
        )
    return response


@router.get("/{topic_id}", response_model=TopicDetailView)
def get_topic_detail(topic_id: int, session: Session = Depends(get_db_session)) -> TopicDetailView:
    repository = TopicRepository(session)
    topic = repository.get_by_id(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")

    news_items = repository.list_news_for_topic(topic.id)
    keywords = _keywords(topic.keywords)
    display_name, alias_zh = topic_naming_fields(
        topic_key=topic.topic_key,
        topic_title=topic.topic_title,
        keywords=keywords,
    )
    return TopicDetailView(
        id=topic.id,
        topic_title=topic.topic_title,
        display_name=display_name,
        alias_zh=alias_zh,
        topic_summary=topic.topic_summary,
        keywords=keywords,
        market=(news_items[0].market if news_items else "us"),
        sentiment_label="positive" if (topic.sentiment_score or 0) > 0.2 else "negative" if (topic.sentiment_score or 0) < -0.2 else "neutral",
        importance_score=topic.importance_score or 0.0,
        news_count=len(news_items),
        last_seen_at=topic.last_seen_at,
        related_symbols=repository.list_related_symbols(topic.id),
        sources=[NewsItemSummary.model_validate(item, from_attributes=True) for item in news_items],
    )
