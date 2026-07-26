from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.simple_cache import JsonBytesTTLCache
from app.db.session import get_db_session
from app.repositories.topic_repository import TopicRepository
from app.schemas.news import NewsItemSummary
from app.schemas.topic import TopicDetailView, TopicItemView
from app.services.topic_naming import topic_naming_fields

router = APIRouter()

# /topics 此前无缓存无分页:每请求全量 topic + 全量关联新闻 + GROUP BY。
# 失效由 app.api.routes.news._clear_routing_caches 统一触发(同一批入库事件)。
#
# FIX-A：缓存内容从「TopicItemView 列表」换成「渲染好的 JSON 字节」。
# /topics 的响应体是全站最大的（全量话题 × 其关联新闻），缓存模型对象时命中路径
# 仍要跑一遍 jsonable_encoder + json.dumps —— 实测这才是 32 并发下 p50 2318ms 的
# 主要来源。改存字节后命中路径只剩一次字典查找 + 字节拷贝。
_topics_cache = JsonBytesTTLCache(ttl=10.0, enabled=get_settings().route_cache_enabled)


def clear_topics_cache() -> None:
    _topics_cache.clear()


def _keywords(raw_keywords: str | None) -> list[str]:
    if not raw_keywords:
        return []
    return [item.strip() for item in raw_keywords.split(",") if item.strip()]


@router.get("", response_model=list[TopicItemView])
def list_topics(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
) -> Response:
    """话题列表。

    limit/offset 为可选分页参数:不传时保持原有的“全量返回”语义(前端契约不变)。
    """
    # 返回类型是 Response（字节直出），但 response_model=list[TopicItemView] 必须保留：
    # OpenAPI schema 仍由它生成，frontend/scripts/generate-api.mjs 依赖它。
    # （说明写在注释里而非 docstring，避免改动 OpenAPI 的 description 字段。）
    cache_key = (limit, offset)
    cached = _topics_cache.cached_response(cache_key)
    if cached is not None:
        return cached

    repository = TopicRepository(session)
    topics = repository.list_all(limit=limit, offset=offset)
    # 批量取数替代逐 topic 的 list_news_for_topic / list_related_symbols，消除 1 + 2T 查询
    topic_ids = [topic.id for topic in topics]
    news_by_topic = repository.batch_news_for_topics(topic_ids)
    symbols_by_topic = repository.batch_related_symbols(topic_ids)
    response: list[TopicItemView] = []
    for topic in topics:
        news_items = news_by_topic.get(topic.id, [])
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
                related_symbols=symbols_by_topic.get(topic.id, []),
            )
        )
    return _topics_cache.store(cache_key, response)


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
