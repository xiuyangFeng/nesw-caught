import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.simple_cache import SimpleTTLCache
from app.db.session import get_db_session
from app.repositories.news_repository import NewsRepository
from app.schemas.llm import NewsAnalysisView
from app.schemas.news import (
    NewsArticleView,
    NewsDetailView,
    NewsEventDetailView,
    NewsFeedLayoutView,
    NewsItemSummary,
    NewsListPageView,
    NewsMentionView,
    NewsTopicRefView,
)
from app.schemas.source_health import NewsRefreshResponse, NewsRuntimeView, SourceFetchResultView
from app.services.event_bus import get_event_bus
from app.services.news_analysis import NewsAnalysisError, NewsAnalysisService
from app.services.news_feed_layout import NewsFeedLayoutService
from app.services.news_ingestion import NewsIngestionService
from app.services.news_runtime import NewsRuntimeService

_route_cache_enabled = get_settings().route_cache_enabled
_feed_layout_cache = SimpleTTLCache(ttl=10.0, enabled=_route_cache_enabled)
_runtime_cache = SimpleTTLCache(ttl=5.0, enabled=_route_cache_enabled)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=NewsListPageView)
def list_news(
    market: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    sentiment_label: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> NewsListPageView:
    repository = NewsRepository(session)
    items, next_cursor = repository.list_recent_page(
        limit=limit,
        cursor=cursor,
        market=market,
        source_name=source_name,
        sentiment_label=sentiment_label,
        query=q,
    )
    return NewsListPageView(
        items=[NewsItemSummary.model_validate(item, from_attributes=True) for item in items],
        next_cursor=next_cursor,
    )


@router.post("/refresh", response_model=NewsRefreshResponse)
def refresh_news_sources(
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(default=False),
    session: Session = Depends(get_db_session)
) -> Any:
    if async_mode:
        def do_async_refresh():
            from app.db.session import SessionLocal
            with SessionLocal() as s:
                try:
                    NewsIngestionService(s).refresh_all()
                except Exception as exc:
                    logger.warning(f"Background ingestion refresh failed: {exc}")

        background_tasks.add_task(do_async_refresh)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=202,
            content={"status": "accepted", "message": "News refresh started in background"}
        )

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
    cache_key = "runtime"
    cached = _runtime_cache.get(cache_key)
    if cached is not None:
        return cached
    view = NewsRuntimeService(session).build()
    _runtime_cache.set(cache_key, view)
    return view


@router.get("/feed-layout", response_model=NewsFeedLayoutView)
def get_news_feed_layout(
    market: str | None = Query(default=None),
    limit_events: int = Query(default=6, ge=1, le=20),
    limit_topics: int = Query(default=6, ge=1, le=20),
    limit_stream: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> NewsFeedLayoutView:
    cache_key = (market, limit_events, limit_topics, limit_stream)
    cached = _feed_layout_cache.get(cache_key)
    if cached is not None:
        return cached
    view = NewsFeedLayoutService(session).build(
        market=market,
        limit_events=limit_events,
        limit_topics=limit_topics,
        limit_stream=limit_stream,
    )
    _feed_layout_cache.set(cache_key, view)
    return view


@router.get("/events/{event_key}", response_model=NewsEventDetailView)
def get_news_event_detail(event_key: str, session: Session = Depends(get_db_session)) -> NewsEventDetailView:
    detail = NewsFeedLayoutService(session).get_event_detail(event_key)
    if detail is None:
        raise HTTPException(status_code=404, detail="event not found")
    return detail


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


def _clear_routing_caches(payload: Any) -> None:
    _feed_layout_cache.clear()
    _runtime_cache.clear()


def register_cache_invalidation(event_bus: Any) -> None:
    """Subscribe cache invalidation handlers on the given event bus.

    Must be called after the application's event bus singleton is finalized
    (see app.main._register_event_handlers), otherwise the handlers would be
    registered on a stale bus instance and never fire.
    """
    event_bus.subscribe("news.signals_processed", _clear_routing_caches)
    event_bus.subscribe("news.created_batch", _clear_routing_caches)
    event_bus.subscribe("news.updated", _clear_routing_caches)
