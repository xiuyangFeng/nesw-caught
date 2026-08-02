import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes import topics as topics_routes
from app.core.config import get_settings
from app.core.simple_cache import JsonBytesTTLCache, json_bytes_response, render_json_bytes
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
from app.services.news_refresh_lease import try_acquire_news_refresh_lease
from app.services.news_runtime import NewsRuntimeService

_route_cache_enabled = get_settings().route_cache_enabled
# FIX-A：以下几个读路径缓存统一存「渲染好的 JSON 字节」而非视图模型对象。
# 存模型对象时，缓存命中虽然省掉了 DB 与业务计算，却没省掉最贵的那段
# —— FastAPI 按 response_model 做的校验 + jsonable_encoder + json.dumps。
# 那段是纯 CPU、被 GIL 串行化，正是 32 并发下 p50 从个位数 ms 劣化到几百 ms 的原因。
_feed_layout_cache = JsonBytesTTLCache(ttl=10.0, enabled=_route_cache_enabled)
_runtime_cache = JsonBytesTTLCache(ttl=5.0, enabled=_route_cache_enabled)
# 事件详情此前完全无缓存,而它正是“点事件卡片”的路径,每次点击都要重跑一遍
# topic 聚合 + O(n²) 融合。TTL 走 settings.event_detail_cache_ttl_seconds。
_event_detail_cache = JsonBytesTTLCache(
    ttl=get_settings().event_detail_cache_ttl_seconds,
    enabled=_route_cache_enabled,
)
# GET /news 此前完全无缓存：每次都要 hydrate 最多 500 行并序列化一遍。
# 这里给一个很短的 TTL（3s）——足够吃掉并发峰值里的重复请求，又不至于让
# “刚入库的新闻迟迟不出现”（何况入库事件会立刻把它清掉，见 _clear_routing_caches）。
_NEWS_LIST_CACHE_TTL_SECONDS = 3.0
_news_list_cache = JsonBytesTTLCache(
    ttl=_NEWS_LIST_CACHE_TTL_SECONDS,
    enabled=_route_cache_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _should_cache_list(q: str | None) -> bool:
    """带搜索词的列表请求不入缓存。

    取舍理由（两条，都指向同一个结论）：
    1. key 基数：``q`` 完全由用户/爬虫控制，每个不同的搜索词都会占一个缓存槽位。
       ``SimpleTTLCache`` 虽有 ``route_cache_max_entries`` 上限 + LRU 兜住内存，
       但那是**共享**容量 —— 一串随机搜索词会把真正的热点 key（前端默认视图的
       market/limit 组合）挤出去，反而让缓存整体命中率归零。
    2. 时效性：搜索是"我刚看到某条新闻，搜一下"的低频交互，对新鲜度的要求高于
       默认信息流，而它的并发量恰恰很低 —— 缓存收益小、风险大。
    非搜索请求（前端默认信息流）才是真正的高并发热点，只缓存这一部分即可。
    """
    return not (q and q.strip())


@router.get("", response_model=NewsListPageView)
def list_news(
    market: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    sentiment_label: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> Response:
    # 返回 Response（JSON 字节直出）以跳过 response_model 的重复序列化；
    # response_model=NewsListPageView 保留，OpenAPI 契约不变。
    # （此处刻意用注释而非 docstring：docstring 会进入 OpenAPI 的 description 字段，
    #  平白改动 frontend/openapi.json。）
    #
    # 缓存 key 必须覆盖【全部】查询参数，否则不同筛选条件会串味。
    # 带 q 的搜索请求刻意绕开缓存，见 _should_cache_list 的说明。
    cache_key = (market, q, source_name, sentiment_label, cursor, limit)
    cacheable = _should_cache_list(q)
    if cacheable:
        cached = _news_list_cache.cached_response(cache_key)
        if cached is not None:
            return cached

    repository = NewsRepository(session)
    items, next_cursor = repository.list_recent_page(
        limit=limit,
        cursor=cursor,
        market=market,
        source_name=source_name,
        sentiment_label=sentiment_label,
        query=q,
    )
    view = NewsListPageView(
        items=[NewsItemSummary.model_validate(item, from_attributes=True) for item in items],
        next_cursor=next_cursor,
    )
    if not cacheable:
        return json_bytes_response(render_json_bytes(view))
    return _news_list_cache.store(cache_key, view)


@router.post("/refresh", response_model=NewsRefreshResponse)
def refresh_news_sources(
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(default=False),
    session: Session = Depends(get_db_session)
) -> Any:
    acquired, retry_after = try_acquire_news_refresh_lease()
    if not acquired:
        retry_seconds = max(1, int(retry_after + 0.999))
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_seconds)},
            content={
                "detail": f"news refresh cooldown active, retry after {retry_seconds}s",
            },
        )

    if async_mode:
        def do_async_refresh():
            from app.db.session import SessionLocal
            with SessionLocal() as s:
                try:
                    NewsIngestionService(s).refresh_all()
                except Exception:
                    logger.exception("Background ingestion refresh failed")

        background_tasks.add_task(do_async_refresh)
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
def get_news_runtime(session: Session = Depends(get_db_session)) -> Response:
    cache_key = "runtime"
    cached = _runtime_cache.cached_response(cache_key)
    if cached is not None:
        return cached
    view = NewsRuntimeService(session).build()
    return _runtime_cache.store(cache_key, view)


@router.get("/feed-layout", response_model=NewsFeedLayoutView)
def get_news_feed_layout(
    market: str | None = Query(default=None),
    limit_events: int = Query(default=6, ge=1, le=20),
    limit_topics: int = Query(default=6, ge=1, le=20),
    limit_stream: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> Response:
    cache_key = (market, limit_events, limit_topics, limit_stream)
    cached = _feed_layout_cache.cached_response(cache_key)
    if cached is not None:
        return cached
    view = NewsFeedLayoutService(session).build(
        market=market,
        limit_events=limit_events,
        limit_topics=limit_topics,
        limit_stream=limit_stream,
    )
    return _feed_layout_cache.store(cache_key, view)


@router.get("/events/{event_key}", response_model=NewsEventDetailView)
def get_news_event_detail(event_key: str, session: Session = Depends(get_db_session)) -> Response:
    cached = _event_detail_cache.cached_response(event_key)
    if cached is not None:
        return cached
    detail = NewsFeedLayoutService(session).get_event_detail(event_key)
    if detail is None:
        # 404 不入缓存:否则任意不存在的 event_key 都能占一个缓存槽位。
        raise HTTPException(status_code=404, detail="event not found")
    return _event_detail_cache.store(event_key, detail)


@router.get("/{news_id}/analysis", response_model=NewsAnalysisView | None)
def get_news_analysis(news_id: int, session: Session = Depends(get_db_session)) -> NewsAnalysisView | None:
    return NewsAnalysisService(session).get_latest(news_id)


def _publish_analysis_completed_event(session: Session, news_id: int, result: NewsAnalysisView) -> None:
    if not (result.analysis_status == "success" and result.top_pick):
        return
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
        logger.exception("failed to publish analysis event: news_id=%s", news_id)


@router.post("/{news_id}/analyze", response_model=NewsAnalysisView)
def analyze_news(
    news_id: int,
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(default=False),
    session: Session = Depends(get_db_session),
) -> Any:
    if async_mode:
        def do_async_analyze():
            from app.db.session import SessionLocal
            with SessionLocal() as s:
                try:
                    result = NewsAnalysisService(s).analyze_news(news_id)
                    _publish_analysis_completed_event(s, news_id, result)
                    # 后台任务不经过 get_db_session 依赖,需要自行提交成功结果
                    # （analyze_news 的成功路径依赖调用方提交，见该方法内注释）。
                    s.commit()
                except Exception:
                    s.rollback()
                    logger.exception("Background news analysis failed for news_id=%s", news_id)

        background_tasks.add_task(do_async_analyze)
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "News analysis started in background",
                "news_id": news_id,
                "status_url": f"/api/news/{news_id}/analysis",
            },
        )

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

    _publish_analysis_completed_event(session, news_id, result)

    return result


@router.get("/{news_id}", response_model=NewsDetailView)
def get_news_detail(news_id: int, session: Session = Depends(get_db_session)) -> NewsDetailView:
    repository = NewsRepository(session)
    bundle = repository.get_detail_bundle(news_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="news not found")

    item, article, topic = bundle.item, bundle.article, bundle.topic
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
            for mention in bundle.mentions
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
    _event_detail_cache.clear()
    # FIX-A 新增的 GET /news 列表字节缓存也吃同一批入库事件：漏掉它会让新入库的
    # 新闻在最长 3s 内不出现在信息流里。
    _news_list_cache.clear()
    # /topics 的缓存也吃同一批入库事件(话题聚合来自同一批新闻),放在这里统一失效,
    # 避免在 topics.py 再挂一套 event bus 订阅。
    topics_routes.clear_topics_cache()


def register_cache_invalidation(event_bus: Any) -> None:
    """Subscribe cache invalidation handlers on the given event bus.

    Must be called after the application's event bus singleton is finalized
    (see app.main._register_event_handlers), otherwise the handlers would be
    registered on a stale bus instance and never fire.
    """
    event_bus.subscribe("news.signals_processed", _clear_routing_caches)
    event_bus.subscribe("news.created_batch", _clear_routing_caches)
    event_bus.subscribe("news.updated", _clear_routing_caches)
