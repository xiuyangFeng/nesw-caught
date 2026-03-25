import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleView, NewsDetailView, NewsItemSummary, NewsMentionView, NewsTopicRefView
from app.schemas.llm import NewsAnalysisView
from app.schemas.source_health import NewsRefreshResponse, SourceFetchResultView, NewsRuntimeView
from app.services.event_bus import get_event_bus
from app.services.news_analysis import NewsAnalysisError, NewsAnalysisService
from app.services.news_ingestion import NewsIngestionService
from app.services.news_runtime import NewsRuntimeService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[NewsItemSummary])
def list_news(
    market: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    sentiment_label: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> list[NewsItemSummary]:
    repository = NewsRepository(session)
    items = repository.list_recent(
        limit=limit,
        market=market,
        source_name=source_name,
        sentiment_label=sentiment_label,
        query=q,
    )
    return [NewsItemSummary.model_validate(item, from_attributes=True) for item in items]


@router.post("/refresh", response_model=NewsRefreshResponse)
def refresh_news_sources(session: Session = Depends(get_db_session)) -> NewsRefreshResponse:
    summary = NewsIngestionService(session).refresh_all()

    return NewsRefreshResponse(
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        fetched_count=summary.fetched_count,
        inserted_count=summary.inserted_count,
        results=[
            SourceFetchResultView(
                source_name=item.source_name,
                source_type=item.source_type,
                status=item.status,
                fetched_count=item.fetched_count,
                inserted_count=item.inserted_count,
                error=item.error,
                latency_ms=item.latency_ms,
            )
            for item in summary.results
        ],
    )


@router.get("/runtime", response_model=NewsRuntimeView)
def get_news_runtime(session: Session = Depends(get_db_session)) -> NewsRuntimeView:
    return NewsRuntimeService(session).build()


@router.get("/{news_id}/analysis", response_model=NewsAnalysisView | None)
def get_news_analysis(news_id: int, session: Session = Depends(get_db_session)) -> NewsAnalysisView | None:
    return NewsAnalysisService(session).get_latest(news_id)


@router.post("/{news_id}/analyze", response_model=NewsAnalysisView)
def analyze_news(news_id: int, session: Session = Depends(get_db_session)) -> NewsAnalysisView:
    service = NewsAnalysisService(session)
    try:
        result = service.analyze_news(news_id)
    except NewsAnalysisError as exc:
        detail = str(exc)
        if detail == "news not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail == "llm provider is not configured":
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=502, detail=detail) from exc

    if result.analysis_status == "success" and result.top_pick:
        try:
            news_repo = NewsRepository(session)
            news_item = news_repo.get_by_id(news_id)
            get_event_bus().publish("news.analysis_completed", {
                "news_id": news_id,
                "news_title": news_item.title if news_item else "",
                "top_pick": result.top_pick.model_dump() if result.top_pick else None,
                "candidates": [c.model_dump() for c in result.candidates],
                "summary": result.summary,
                "risk_notes": result.risk_notes,
            })
        except Exception:
            logger.exception("failed to publish analysis event")

    return result


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
