"""WS-2：重读接口与查询优化的回归测试。

覆盖的性能契约（数字均在注释里写明“改之前/改之后”）：

1. feed-layout 带 market 参数时，market 条件出现在 SQL 里（不再是先全量 hydrate 再在
   Python 里筛）；
2. `GET /news/events/{event_key}` 的 TTL 缓存命中（第二次请求零 DB 查询）与失效
   （publish news.created_batch 后缓存被清）；
3. 事件详情路径上 `build_event_cards` 只跑一次（旧实现跑两遍，等于 O(n²) 融合算法跑两次）；
4. `NewsFeedLayoutService.build()` 的 DB 往返次数上界；
5. 一条新闻挂多个 TopicNewsLink 时 `get_detail_bundle` 的取值是确定的（旧实现随机）。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from app.api.routes import news as news_routes
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_repository import NewsRepository
from app.repositories.topic_repository import TopicRepository
from app.services import news_feed_layout as feed_layout_module
from app.services.event_bus import HybridEventBus
from app.services.news_feed_layout import TOPIC_CANDIDATE_LIMIT, NewsFeedLayoutService

_NOW = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
_PREFIX = "ws2"


# ---------------------------------------------------------------------------
# 工具：SQL 语句捕获
# ---------------------------------------------------------------------------


class _StatementRecorder:
    def __init__(self) -> None:
        self.statements: list[tuple[str, object]] = []

    @property
    def selects(self) -> list[tuple[str, object]]:
        return [item for item in self.statements if item[0].lstrip().upper().startswith("SELECT")]

    def find(self, needle: str) -> list[tuple[str, object]]:
        return [item for item in self.selects if needle in item[0]]


@contextmanager
def capture_sql():
    recorder = _StatementRecorder()

    def _listener(_conn, _cursor, statement, parameters, _context, _executemany) -> None:
        recorder.statements.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        yield recorder
    finally:
        event.remove(engine, "before_cursor_execute", _listener)


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


def _make_news(
    suffix: str,
    *,
    market: str,
    source: str,
    title: str,
    published_at: datetime,
) -> NewsItem:
    return NewsItem(
        source_name=source,
        source_url="https://example.com/rss",
        title=title,
        summary=f"summary for {suffix}",
        canonical_url=f"https://example.com/{_PREFIX}-{suffix}",
        url_hash=f"{_PREFIX}-{suffix}",
        market=market,
        language="en",
        published_at=published_at,
        fetched_at=published_at + timedelta(minutes=1),
        ingest_status="ingested",
    )


def _cleanup() -> None:
    with SessionLocal() as session:
        news_ids = select(NewsItem.id).where(NewsItem.url_hash.like(f"{_PREFIX}-%"))
        topic_ids = select(TopicCluster.id).where(TopicCluster.topic_key.like(f"{_PREFIX}-%"))
        session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
        session.execute(delete(TopicNewsLink).where(TopicNewsLink.topic_cluster_id.in_(topic_ids)))
        session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(news_ids)))
        session.execute(delete(TopicCluster).where(TopicCluster.topic_key.like(f"{_PREFIX}-%")))
        session.execute(delete(NewsItem).where(NewsItem.url_hash.like(f"{_PREFIX}-%")))
        session.commit()


@pytest.fixture()
def seeded_topic() -> dict[str, int]:
    """一个跨市场话题：2 条 us 新闻 + 1 条 hk 新闻，各自带 mention。"""
    _cleanup()
    with SessionLocal() as session:
        news_items = [
            _make_news(
                "us-1",
                market="us",
                source="Reuters",
                title="NVIDIA launches new AI chip platform",
                published_at=_NOW - timedelta(minutes=10),
            ),
            _make_news(
                "us-2",
                market="us",
                source="Bloomberg",
                title="Suppliers rally after NVIDIA chip release",
                published_at=_NOW - timedelta(minutes=20),
            ),
            _make_news(
                "hk-1",
                market="hk",
                source="AAStocks",
                title="Tencent AI product update",
                published_at=_NOW - timedelta(minutes=30),
            ),
        ]
        session.add_all(news_items)
        session.flush()

        topic = TopicCluster(
            topic_key=f"{_PREFIX}-topic-ai",
            topic_title="WS2 AI Chip Launch",
            topic_summary="Cross market AI product topic.",
            keywords="nvidia,chip,launch,ai",
            sentiment_score=0.5,
            # 远高于种子数据/其它用例，保证一定落在 TOPIC_CANDIDATE_LIMIT 候选池里
            importance_score=99.5,
            last_seen_at=_NOW,
        )
        session.add(topic)
        session.flush()
        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[0].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[1].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[2].id),
                NewsStockMention(
                    news_id=news_items[0].id,
                    symbol="NVDA",
                    market="us",
                    mention_type="body",
                    confidence=0.9,
                ),
                NewsStockMention(
                    news_id=news_items[2].id,
                    symbol="0700.HK",
                    market="hk",
                    mention_type="body",
                    confidence=0.9,
                ),
            ]
        )
        session.commit()
        ids = {
            "topic_id": topic.id,
            "us_1": news_items[0].id,
            "us_2": news_items[1].id,
            "hk_1": news_items[2].id,
        }
    yield ids
    _cleanup()


def _event_key_for(title: str) -> str:
    """按事件标题反查 event_key。

    种子演示数据里可能存在与被测话题同类型/同 symbol 的话题，融合后 event_key 会变成
    `fused-topic-a-topic-b`，因此不能把 `topic-{id}` 写死在断言里。
    """
    with SessionLocal() as session:
        service = NewsFeedLayoutService(session)
        topic_views, topic_news_map, topic_mentions_map = service._collect_topic_context()
        cards = feed_layout_module.build_event_cards(
            topic_views,
            topic_news_map=topic_news_map,
            topic_mentions_map=topic_mentions_map,
            max_news_items=None,
        )
    return next(card.event_key for card in cards if card.event_title == title)


@pytest.fixture()
def enabled_event_detail_cache():
    cache = news_routes._event_detail_cache
    previous = cache.enabled
    cache.enabled = True
    cache.clear()
    yield cache
    cache.enabled = previous
    cache.clear()


# ---------------------------------------------------------------------------
# 1. market 过滤下推到 SQL
# ---------------------------------------------------------------------------


def test_market_filter_is_pushed_down_to_sql(seeded_topic) -> None:
    """旧实现：batch_news_for_topics 的 SQL 完全不带 market，带 market 的请求照样把
    全市场新闻拉进内存再在 Python 里丢掉。现在 market 必须出现在 SQL 条件里。"""
    topic_id = seeded_topic["topic_id"]

    with SessionLocal() as session, capture_sql() as recorder:
        service = NewsFeedLayoutService(session)
        _topic_views, topic_news_map, _mentions = service._collect_topic_context(market="us")

    topic_news_statements = recorder.find("topic_news_link")
    assert topic_news_statements, "未捕获到 topic 关联新闻的查询"
    # 关联新闻查询里必须带 news_item.market 条件
    news_join_statement = next(
        (stmt for stmt, _params in topic_news_statements if "news_item.market" in stmt),
        None,
    )
    assert news_join_statement is not None, (
        "batch_news_for_topics 的 SQL 未包含 market 条件：\n"
        + "\n".join(stmt for stmt, _ in topic_news_statements)
    )

    # 结果侧同样只含目标市场
    items = topic_news_map[topic_id]
    assert {item.market for item in items} == {"us"}
    assert len(items) == 2


def test_market_filtered_feed_layout_returns_only_that_market(seeded_topic) -> None:
    with SessionLocal() as session:
        view = NewsFeedLayoutService(session).build(market="us")

    card = next(c for c in view.events if c.event_title == "WS2 AI Chip Launch")
    assert card.market == "us"
    assert card.news_count == 2  # hk 那条不计入
    assert {item.market for item in card.news_items} == {"us"}
    assert card.related_symbols == ["NVDA"]


def test_collect_topic_context_limits_topic_candidates(seeded_topic, monkeypatch) -> None:
    """topic 候选池必须限量：旧实现无条件 list_all()（线上 334 条）。"""
    seen: list[int | None] = []
    original = TopicRepository.list_all

    def _spy(self, *, limit=None, offset=0):
        seen.append(limit)
        return original(self, limit=limit, offset=offset)

    monkeypatch.setattr(TopicRepository, "list_all", _spy)

    with SessionLocal() as session:
        NewsFeedLayoutService(session).build()
        NewsFeedLayoutService(session).get_event_detail("topic-does-not-exist")

    # feed-layout 与事件详情必须用同一个候选池上限，否则融合出的 event_key 对不上
    assert seen == [TOPIC_CANDIDATE_LIMIT, TOPIC_CANDIDATE_LIMIT]


# ---------------------------------------------------------------------------
# 2. 事件详情路由缓存：命中 + 失效
# ---------------------------------------------------------------------------


def test_event_detail_route_is_cached_and_invalidated(
    seeded_topic, enabled_event_detail_cache
) -> None:
    event_key = _event_key_for("WS2 AI Chip Launch")
    client = TestClient(app)

    with capture_sql() as first:
        first_response = client.get(f"/api/news/events/{event_key}")
    assert first_response.status_code == 200
    assert len(first.selects) > 0, "首次请求应当真的查库"

    with capture_sql() as second:
        second_response = client.get(f"/api/news/events/{event_key}")
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    # 缓存命中：第二次请求不再触发任何 SELECT
    assert second.selects == [], f"缓存未命中，仍执行了 {len(second.selects)} 条查询"

    # 失效：news.created_batch 必须把事件详情缓存一起清掉
    bus = HybridEventBus(backend="memory")
    news_routes.register_cache_invalidation(bus)
    bus.publish("news.created_batch", {"news_ids": []})

    with capture_sql() as third:
        third_response = client.get(f"/api/news/events/{event_key}")
    assert third_response.status_code == 200
    assert len(third.selects) > 0, "缓存失效后应重新查库"


def test_event_detail_404_is_not_cached(seeded_topic, enabled_event_detail_cache) -> None:
    client = TestClient(app)
    response = client.get("/api/news/events/topic-999999999")
    assert response.status_code == 404
    assert enabled_event_detail_cache.get("topic-999999999") is None


# ---------------------------------------------------------------------------
# 3. 事件详情路径只跑一次 build_event_cards
# ---------------------------------------------------------------------------


def test_event_detail_builds_event_cards_once(seeded_topic, monkeypatch) -> None:
    """旧实现在 _build_event_detail 里调用 build_event_cards 两次（第二次
    max_news_items=None），O(n²) 融合算法整整跑两遍。"""
    calls: list[object] = []
    original = feed_layout_module.build_event_cards

    def _counting(*args, **kwargs):
        calls.append(kwargs.get("max_news_items", 3))
        return original(*args, **kwargs)

    event_key = _event_key_for("WS2 AI Chip Launch")
    monkeypatch.setattr(feed_layout_module, "build_event_cards", _counting)

    with SessionLocal() as session:
        detail = NewsFeedLayoutService(session).get_event_detail(event_key)

    assert detail is not None
    assert len(calls) == 1, f"build_event_cards 被调用 {len(calls)} 次，应为 1 次"
    # 唯一那次必须是“完整版”，详情页不能截断新闻列表
    assert calls[0] is None
    # 详情页不截断：news_count 与实际条数一致，且包含被测话题的全部 3 条新闻
    assert detail.news_count == len(detail.news_items)
    assert detail.news_count >= 3
    seeded_ids = {seeded_topic["us_1"], seeded_topic["us_2"], seeded_topic["hk_1"]}
    assert seeded_ids <= {item.id for item in detail.news_items}


def test_event_detail_matches_two_pass_reference(seeded_topic) -> None:
    """单次构建的详情结果必须与旧的“两遍构建”参照实现逐字段一致。"""
    event_key = _event_key_for("WS2 AI Chip Launch")
    with SessionLocal() as session:
        service = NewsFeedLayoutService(session)
        topic_views, topic_news_map, topic_mentions_map = service._collect_topic_context()
        watchlist_items = service.watchlist_repository.list_all()

        current = service._build_event_detail(
            event_key,
            topic_views=topic_views,
            topic_news_map=topic_news_map,
            topic_mentions_map=topic_mentions_map,
            watchlist_items=watchlist_items,
        )

        # 旧实现参照：先 max_news_items=3 取头部字段，再 max_news_items=None 取完整列表
        short_cards = feed_layout_module._attach_watchlist_hits(
            feed_layout_module.build_event_cards(
                topic_views,
                topic_news_map=topic_news_map,
                topic_mentions_map=topic_mentions_map,
            ),
            watchlist_items,
        )
        full_cards = feed_layout_module._attach_watchlist_hits(
            feed_layout_module.build_event_cards(
                topic_views,
                topic_news_map=topic_news_map,
                topic_mentions_map=topic_mentions_map,
                max_news_items=None,
            ),
            watchlist_items,
        )
        short = next(c for c in short_cards if c.event_key == event_key)
        full = next(c for c in full_cards if c.event_key == event_key)
        expected_news = sorted(
            full.news_items, key=feed_layout_module._news_sort_key, reverse=True
        )
        payload = short.model_dump()
        payload["news_count"] = len(expected_news)
        payload["source_count"] = len({item.source_name for item in expected_news})
        payload["news_items"] = expected_news
        reference = feed_layout_module.NewsEventDetailView(**payload)

    assert current is not None
    assert current.model_dump() == reference.model_dump()


# ---------------------------------------------------------------------------
# 4. build() 的 DB 往返次数上界
# ---------------------------------------------------------------------------

# NewsFeedLayoutService.build() 的查询构成（改前改后都是这 5 条，重构没有引入新往返，
# 但每条扫/搬的行数大幅下降）：
#   1) news_item 最近列表（stream）
#   2) topic_cluster 候选池（改前无 LIMIT 全量 334 条 → 改后 LIMIT 60）
#   3) topic_news_link ⋈ news_item（改前无 market 条件、全量 533 行 → 改后 market 下推 + 候选池收窄）
#   4) news_stock_mention 批量聚合
#   5) watchlist_item 全量
MAX_BUILD_QUERIES = 5

# 事件详情路径 = build() 去掉 stream 那条。
MAX_EVENT_DETAIL_QUERIES = 4


def test_build_query_roundtrips_are_bounded(seeded_topic) -> None:
    with SessionLocal() as session, capture_sql() as recorder:
        NewsFeedLayoutService(session).build()
    assert len(recorder.selects) <= MAX_BUILD_QUERIES, "\n".join(
        stmt for stmt, _ in recorder.selects
    )


def test_build_with_market_query_roundtrips_are_bounded(seeded_topic) -> None:
    with SessionLocal() as session, capture_sql() as recorder:
        NewsFeedLayoutService(session).build(market="us")
    assert len(recorder.selects) <= MAX_BUILD_QUERIES, "\n".join(
        stmt for stmt, _ in recorder.selects
    )


def test_event_detail_query_roundtrips_are_bounded(seeded_topic) -> None:
    event_key = _event_key_for("WS2 AI Chip Launch")
    with SessionLocal() as session, capture_sql() as recorder:
        NewsFeedLayoutService(session).get_event_detail(event_key)
    assert len(recorder.selects) <= MAX_EVENT_DETAIL_QUERIES, "\n".join(
        stmt for stmt, _ in recorder.selects
    )


def test_source_weight_map_is_resolved_once_per_build(seeded_topic, monkeypatch) -> None:
    """旧实现 build_event_cards 与 _stream_editorial_scores 各调一次 _source_weight_map()
    → 每请求两次 load_sources() → 两次 os.stat。"""
    calls = {"n": 0}
    original = feed_layout_module._source_weight_map

    def _counting():
        calls["n"] += 1
        return original()

    monkeypatch.setattr(feed_layout_module, "_source_weight_map", _counting)

    with SessionLocal() as session:
        NewsFeedLayoutService(session).build()

    assert calls["n"] == 1, f"_source_weight_map 每请求被调用 {calls['n']} 次，应为 1 次"


# ---------------------------------------------------------------------------
# 5. get_detail_bundle 在多 topic link 下的确定性
# ---------------------------------------------------------------------------


def test_get_detail_bundle_picks_deterministic_topic() -> None:
    """一条新闻挂多个 TopicNewsLink 时，ArticleContent × TopicNewsLink 产生笛卡尔行，
    旧实现的 .first() 取到的是任意一条 topic。现在规则固定为
    importance_score 降序 → last_seen_at 降序 → id 降序。"""
    _cleanup()
    try:
        with SessionLocal() as session:
            item = _make_news(
                "bundle-1",
                market="us",
                source="Reuters",
                title="Multi topic story",
                published_at=_NOW,
            )
            session.add(item)
            session.flush()

            topics = [
                TopicCluster(
                    topic_key=f"{_PREFIX}-bundle-low",
                    topic_title="WS2 Low Importance",
                    importance_score=0.1,
                    last_seen_at=_NOW,
                ),
                TopicCluster(
                    topic_key=f"{_PREFIX}-bundle-high",
                    topic_title="WS2 High Importance",
                    importance_score=0.9,
                    last_seen_at=_NOW - timedelta(days=1),
                ),
                TopicCluster(
                    topic_key=f"{_PREFIX}-bundle-mid",
                    topic_title="WS2 Mid Importance",
                    importance_score=0.5,
                    last_seen_at=_NOW,
                ),
            ]
            session.add_all(topics)
            session.flush()
            session.add_all(
                [TopicNewsLink(topic_cluster_id=t.id, news_id=item.id) for t in topics]
            )
            session.commit()
            news_id = item.id

        # 多次读取必须稳定返回 importance_score 最高的那个 topic
        picked = []
        for _ in range(5):
            with SessionLocal() as session:
                bundle = NewsRepository(session).get_detail_bundle(news_id)
                assert bundle is not None
                assert bundle.topic is not None
                picked.append(bundle.topic.topic_title)
        assert set(picked) == {"WS2 High Importance"}
    finally:
        _cleanup()


def test_get_detail_bundle_tie_breaks_on_last_seen_then_id() -> None:
    """importance_score 相同时按 last_seen_at 降序，再相同按 id 降序。"""
    _cleanup()
    try:
        with SessionLocal() as session:
            item = _make_news(
                "bundle-2",
                market="us",
                source="Reuters",
                title="Tie break story",
                published_at=_NOW,
            )
            session.add(item)
            session.flush()
            older = TopicCluster(
                topic_key=f"{_PREFIX}-tie-older",
                topic_title="WS2 Tie Older",
                importance_score=0.7,
                last_seen_at=_NOW - timedelta(hours=2),
            )
            newer = TopicCluster(
                topic_key=f"{_PREFIX}-tie-newer",
                topic_title="WS2 Tie Newer",
                importance_score=0.7,
                last_seen_at=_NOW,
            )
            session.add_all([older, newer])
            session.flush()
            session.add_all(
                [
                    TopicNewsLink(topic_cluster_id=older.id, news_id=item.id),
                    TopicNewsLink(topic_cluster_id=newer.id, news_id=item.id),
                ]
            )
            session.commit()
            news_id = item.id

        with SessionLocal() as session:
            bundle = NewsRepository(session).get_detail_bundle(news_id)
            assert bundle is not None and bundle.topic is not None
            assert bundle.topic.topic_title == "WS2 Tie Newer"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# 6. 融合的分词 memo / 分桶不改变语义
# ---------------------------------------------------------------------------


def test_fuse_event_cards_semantics_unchanged_by_memoization() -> None:
    """分词 memo + 按 event_type 分桶只是剪掉必然为 False 的比较，融合结果不变。"""
    from app.schemas.news import NewsFeedEventCardView

    def _card(key: str, title: str, event_type: str, primary: str | None, related: list[str]):
        return NewsFeedEventCardView(
            event_key=key,
            event_title=title,
            event_summary=None,
            event_type=event_type,
            market="us",
            sentiment_label="neutral",
            importance_score=0.8,
            last_seen_at=_NOW,
            primary_symbol=primary,
            related_symbols=related,
            source_count=1,
            news_count=0,
            news_items=[],
        )

    cards = [
        _card("topic-1", "NVIDIA AI chip launch", "product", "NVDA", ["NVDA", "SMCI"]),
        _card("topic-2", "NVIDIA AI chip release", "product", None, ["NVDA", "AMD"]),
        _card("topic-3", "Fed rate decision", "macro", None, ["SPY"]),
        _card("topic-4", "Company update", "general", "NVDA", ["NVDA"]),
        _card("topic-5", "Another company update", "general", "NVDA", ["NVDA"]),
        _card("topic-6", "Chip supply squeeze", "supply_chain", None, ["NVDA", "AMD", "TSMC"]),
        _card("topic-7", "Chip demand rebound", "supply_chain", None, ["NVDA", "AMD", "INTC"]),
    ]

    fused = feed_layout_module.fuse_event_cards(cards)
    keys = [card.event_key for card in fused]

    # topic-1/2 同 primary/标题重合 → 融合；general 的两张永不融合；6/7 symbol 重合 ≥2 → 融合
    assert keys == [
        "fused-topic-1-topic-2",
        "topic-3",
        "topic-4",
        "topic-5",
        "fused-topic-6-topic-7",
    ]
