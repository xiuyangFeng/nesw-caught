"""FIX-A：读接口响应字节缓存的回归测试。

背景（实测数据，211 条新闻的库，32 并发）：

    端点                      串行      并发32 p50    p95
    /news?limit=200           3.0ms     623ms       870ms
    /topics                  10.0ms    2318ms      3238ms

串行只要个位数毫秒，32 并发却劣化到几百毫秒 —— 这不是 DB 的问题（/topics 本来就有
TTL 缓存），而是**纯 CPU 且被 GIL 串行化**的响应序列化开销：缓存里存的是 Pydantic
模型对象，FastAPI 在返回时仍要按 response_model 做一次完整的校验 + jsonable_encoder
+ json.dumps。缓存命中省掉了 DB 和业务计算，却没省掉最贵的那一段。

改法：缓存「已渲染好的 JSON 字节」，命中时直接返回 ``Response`` —— FastAPI 见到
``Response`` 实例就会跳过 response_model 的校验与序列化，把字节直接写出去。

本文件锁住的契约：
1. **字节等价性**（最重要）：字节缓存吐出的响应，必须与「改造前 FastAPI 按
   response_model 原生序列化模型对象」的响应逐字段完全相等；
2. 缓存命中不再触发序列化（jsonable_encoder / model_dump 调用数为 0）；
3. 缓存命中不再触发任何 SELECT；
4. news.created_batch 等入库事件能把**全部**读路径缓存（含新增的 /news 列表缓存）清掉；
5. /news 列表缓存的 key 必须覆盖全部查询参数，不同筛选条件之间不串味；
6. route_cache_enabled=false 时行为与改造前完全一致（每次都查库，响应体不变）。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from app.api.routes import news as news_routes
from app.api.routes import topics as topics_routes
from app.core import simple_cache as simple_cache_module
from app.core.simple_cache import JsonBytesTTLCache
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.schemas.topic import TopicItemView
from app.services import news_feed_layout as feed_layout_module
from app.services.event_bus import HybridEventBus
from app.services.news_feed_layout import NewsFeedLayoutService

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_PREFIX = "fixa"

# 被测的五个读端点：(路由 path, 请求 URL 模板)
_NEWS_PATH = "/api/news"
_TOPICS_PATH = "/api/topics"
_RUNTIME_PATH = "/api/news/runtime"
_FEED_LAYOUT_PATH = "/api/news/feed-layout"
_EVENT_DETAIL_PATH = "/api/news/events/{event_key}"

_ALL_CACHES = (
    news_routes._news_list_cache,
    news_routes._feed_layout_cache,
    news_routes._runtime_cache,
    news_routes._event_detail_cache,
    topics_routes._topics_cache,
)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


class _StatementRecorder:
    def __init__(self) -> None:
        self.statements: list[str] = []

    @property
    def selects(self) -> list[str]:
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]


@contextmanager
def capture_sql():
    recorder = _StatementRecorder()

    def _listener(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        recorder.statements.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        yield recorder
    finally:
        event.remove(engine, "before_cursor_execute", _listener)


@contextmanager
def count_encodes(monkeypatch):
    """统计真正发生的 JSON 序列化次数。

    ``render_json_bytes`` 是全部字节缓存的唯一渲染入口（``JsonBytesTTLCache.store``
    调用的就是它）。命中缓存时这里必须为 0。
    """
    calls: list[object] = []
    original = simple_cache_module.render_json_bytes

    def _counting(payload):
        calls.append(payload)
        return original(payload)

    monkeypatch.setattr(simple_cache_module, "render_json_bytes", _counting)
    try:
        yield calls
    finally:
        monkeypatch.setattr(simple_cache_module, "render_json_bytes", original)


def _route_response_model(path: str):
    """取出路由上声明的 response_model —— 字节等价性必须以它为准。"""
    for route in app.routes:
        if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set()):
            return route.response_model
    raise AssertionError(f"未找到路由 {path}")


def _fastapi_reference_bytes(response_model, view) -> bytes:
    """用 FastAPI 原生 response_model 链路渲染 —— 即"改造前"的响应字节。

    这里刻意起一个真实的 FastAPI 应用并走 TestClient，而不是手工拼 json.dumps：
    只有这样才能把 response_model 校验、by_alias、datetime 编码、
    ``JSONResponse.render()`` 的分隔符/ensure_ascii 等全部细节一并覆盖到。
    """
    reference_app = FastAPI()

    @reference_app.get("/ref", response_model=response_model)
    def _ref():  # pragma: no cover - 仅在测试内被 TestClient 调用
        return view

    with TestClient(reference_app) as client:
        response = client.get("/ref")
    assert response.status_code == 200
    return response.content


@contextmanager
def capture_cached_views(monkeypatch):
    """截获各路由塞进字节缓存之前的视图模型对象，供参照实现使用。"""
    captured: list[object] = []
    original = JsonBytesTTLCache.store

    def _spy(self, key, payload):
        captured.append(payload)
        return original(self, key, payload)

    monkeypatch.setattr(JsonBytesTTLCache, "store", _spy)
    try:
        yield captured
    finally:
        monkeypatch.setattr(JsonBytesTTLCache, "store", original)


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
def seeded() -> dict[str, int]:
    """跨市场数据：2 条 us + 1 条 hk，挂在同一个高权重话题下。

    刻意让 summary / title 里带非 ASCII 与 None 字段，把字节等价性里最容易出问题的
    ``ensure_ascii`` 与 null 处理一起覆盖掉。
    """
    _cleanup()
    with SessionLocal() as session:
        items = [
            _make_news(
                "us-1",
                market="us",
                source="Reuters",
                title="NVIDIA 发布新一代 AI 芯片平台",
                published_at=_NOW - timedelta(minutes=10),
            ),
            _make_news(
                "us-2",
                market="us",
                source="Bloomberg",
                title="Suppliers rally after chip release",
                published_at=_NOW - timedelta(minutes=20),
            ),
            _make_news(
                "hk-1",
                market="hk",
                source="AAStocks",
                title="腾讯 AI 产品更新",
                published_at=_NOW - timedelta(minutes=30),
            ),
        ]
        # 显式留一个 None 字段：字节等价性必须覆盖 null 的序列化
        items[1].summary = None
        session.add_all(items)
        session.flush()

        topic = TopicCluster(
            topic_key=f"{_PREFIX}-topic-ai",
            topic_title="FIXA AI Chip Launch",
            topic_summary="跨市场 AI 产品话题。",
            keywords="nvidia,chip,launch,ai",
            sentiment_score=0.5,
            importance_score=99.5,
            last_seen_at=_NOW,
        )
        session.add(topic)
        session.flush()
        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topic.id, news_id=items[0].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=items[1].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=items[2].id),
                NewsStockMention(
                    news_id=items[0].id,
                    symbol="NVDA",
                    market="us",
                    mention_type="body",
                    confidence=0.9,
                ),
            ]
        )
        session.commit()
        ids = {
            "topic_id": topic.id,
            "us_1": items[0].id,
            "us_2": items[1].id,
            "hk_1": items[2].id,
        }
    yield ids
    _cleanup()


@pytest.fixture()
def enabled_caches():
    """全局 conftest 关掉了路由缓存，这里按实例重新打开。"""
    previous = [cache.enabled for cache in _ALL_CACHES]
    for cache in _ALL_CACHES:
        cache.enabled = True
        cache.clear()
    yield
    for cache, was_enabled in zip(_ALL_CACHES, previous, strict=True):
        cache.enabled = was_enabled
        cache.clear()


@pytest.fixture()
def disabled_caches():
    previous = [cache.enabled for cache in _ALL_CACHES]
    for cache in _ALL_CACHES:
        cache.enabled = False
        cache.clear()
    yield
    for cache, was_enabled in zip(_ALL_CACHES, previous, strict=True):
        cache.enabled = was_enabled
        cache.clear()


@pytest.fixture(autouse=True)
def restore_event_bus_singleton():
    """兜底修复会话级污染：全量跑时 test_market.py 会把全局 event bus 单例换成一个
    只有 publish/subscribe 的 FakeBus 且不还原，而 /news/runtime 要向它取
    ``get_status()``。这里在本文件范围内换回真实实例，用完还原。
    """
    import app.services.event_bus as event_bus_module

    previous = event_bus_module._instance
    event_bus_module._instance = HybridEventBus(backend="memory")
    try:
        yield
    finally:
        event_bus_module._instance = previous


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _event_key(title: str = "FIXA AI Chip Launch") -> str:
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


def _endpoints(seeded_ids: dict[str, int]) -> list[tuple[str, str, str]]:
    """(用例名, 请求 URL, 路由 path)"""
    event_key = _event_key()
    return [
        ("news-list", "/api/news?limit=200", _NEWS_PATH),
        ("news-list-market", "/api/news?market=us&limit=50", _NEWS_PATH),
        ("topics", "/api/topics", _TOPICS_PATH),
        ("runtime", "/api/news/runtime", _RUNTIME_PATH),
        ("feed-layout", "/api/news/feed-layout", _FEED_LAYOUT_PATH),
        ("event-detail", f"/api/news/events/{event_key}", _EVENT_DETAIL_PATH),
    ]


# ---------------------------------------------------------------------------
# 1. 字节等价性（硬要求）
# ---------------------------------------------------------------------------


def test_cached_bytes_match_fastapi_native_serialization(
    seeded, enabled_caches, client, monkeypatch
) -> None:
    """核心断言：字节缓存的响应 == 改造前 FastAPI 按 response_model 原生序列化的响应。

    参照实现不是手写的 json.dumps，而是一个真实的 FastAPI 路由（同一个
    response_model，返回模型对象），因此字段集合、字段顺序、null、datetime 格式、
    非 ASCII 转义、分隔符全部都在比较范围内。
    """
    for name, url, route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()

        # miss：截获路由塞进缓存前的视图模型
        with capture_cached_views(monkeypatch) as captured:
            miss = client.get(url)
        assert miss.status_code == 200, name
        assert len(captured) == 1, f"{name}: 期望恰好一次缓存写入，实际 {len(captured)}"
        view = captured[0]

        # hit：走字节直出
        hit = client.get(url)
        assert hit.status_code == 200, name

        reference = _fastapi_reference_bytes(_route_response_model(route_path), view)

        assert miss.content == reference, f"{name}: miss 响应字节与 FastAPI 原生序列化不一致"
        assert hit.content == reference, f"{name}: 缓存命中的字节与 FastAPI 原生序列化不一致"
        assert hit.json() == miss.json() == _bytes_to_json(reference), name
        assert hit.headers["content-type"].startswith("application/json"), name


def _bytes_to_json(raw: bytes):
    import json

    return json.loads(raw)


def test_cached_and_uncached_responses_are_identical(seeded, client) -> None:
    """同一份数据，缓存关闭 / 缓存命中两条路径的 JSON 必须完全相等。"""
    for _name, url, _route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.enabled = False
            cache.clear()
        uncached_a = client.get(url)
        uncached_b = client.get(url)

        for cache in _ALL_CACHES:
            cache.enabled = True
            cache.clear()
        cached_miss = client.get(url)
        cached_hit = client.get(url)

        for cache in _ALL_CACHES:
            cache.enabled = False
            cache.clear()

        assert uncached_a.json() == uncached_b.json() == cached_miss.json() == cached_hit.json()
        assert cached_miss.content == cached_hit.content == uncached_a.content


def test_non_ascii_and_null_fields_survive_the_byte_cache(seeded, enabled_caches, client) -> None:
    """字节缓存最容易踩的两个坑：中文被转义成 \\uXXXX、None 变成缺字段。"""
    news_routes._news_list_cache.clear()
    first = client.get("/api/news?limit=200")
    second = client.get("/api/news?limit=200")

    titles = {item["title"] for item in second.json()["items"]}
    assert "NVIDIA 发布新一代 AI 芯片平台" in titles
    # 中文必须以 UTF-8 原样落在响应体里（ensure_ascii=False），而不是 \uXXXX
    assert "发布新一代".encode() in second.content
    assert b"\\u53d1" not in second.content

    us_2 = next(item for item in second.json()["items"] if item["title"].startswith("Suppliers"))
    assert "summary" in us_2 and us_2["summary"] is None, "None 字段必须保留为显式 null"
    assert first.content == second.content


# ---------------------------------------------------------------------------
# 2. 缓存命中不再序列化
# ---------------------------------------------------------------------------


def test_cache_hit_skips_serialization(seeded, enabled_caches, client, monkeypatch) -> None:
    for name, url, _route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()

        with count_encodes(monkeypatch) as calls:
            first = client.get(url)
            assert first.status_code == 200, name
            assert len(calls) == 1, f"{name}: miss 时应恰好序列化一次，实际 {len(calls)}"

            calls.clear()
            second = client.get(url)
            assert second.status_code == 200, name
            assert calls == [], f"{name}: 缓存命中仍然做了 {len(calls)} 次序列化"


def test_routes_never_enter_fastapi_serialize_response(
    seeded, enabled_caches, client, monkeypatch
) -> None:
    """直接锁住 FIX-A 的机制本身。

    FastAPI(0.135) 对"返回非 Response 对象"的 handler 会调用
    ``fastapi.routing.serialize_response()``：先按 response_model **重新校验**整棵
    对象树（几百个模型对象，这是大头），再序列化成 JSON。handler 返回 ``Response``
    时这个函数完全不会被调用。

    因此这里断言：改造后的五个读端点，miss 与 hit 都不再进入 serialize_response，
    而同样数据的参照实现（返回模型对象）每次都会进 —— 证明计数器确实有效。
    """
    import fastapi.routing as fastapi_routing

    calls: list[object] = []
    original = fastapi_routing.serialize_response

    async def _counting(*args, **kwargs):
        calls.append(kwargs.get("field"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(fastapi_routing, "serialize_response", _counting)

    for name, url, route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()

        calls.clear()
        with capture_cached_views(monkeypatch) as captured:
            miss = client.get(url)
        assert miss.status_code == 200, name
        assert calls == [], f"{name}: miss 路径仍进入了 serialize_response"
        view = captured[0]

        calls.clear()
        hit = client.get(url)
        assert hit.status_code == 200, name
        assert calls == [], f"{name}: 缓存命中仍进入了 serialize_response"

        # 对照组：返回模型对象的参照实现每次都要进 serialize_response
        calls.clear()
        reference = _fastapi_reference_bytes(_route_response_model(route_path), view)
        assert len(calls) == 1, f"{name}: 参照实现应当进入 serialize_response"
        assert miss.content == hit.content == reference, name


# ---------------------------------------------------------------------------
# 3. 缓存命中不再查库
# ---------------------------------------------------------------------------


def test_cache_hit_issues_no_sql(seeded, enabled_caches, client) -> None:
    for name, url, _route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()

        with capture_sql() as first:
            assert client.get(url).status_code == 200, name
        assert first.selects, f"{name}: 首次请求应当真的查库"

        with capture_sql() as second:
            assert client.get(url).status_code == 200, name
        assert second.selects == [], f"{name}: 缓存命中仍执行了 {len(second.selects)} 条 SELECT"


# ---------------------------------------------------------------------------
# 4. 失效
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_name",
    ["news.created_batch", "news.updated", "news.signals_processed"],
)
def test_invalidation_clears_every_read_cache(
    seeded, enabled_caches, client, event_name
) -> None:
    urls = [url for _name, url, _path in _endpoints(seeded)]
    for url in urls:
        assert client.get(url).status_code == 200
        assert client.get(url).status_code == 200  # 确保都进了缓存

    with capture_sql() as warm:
        for url in urls:
            client.get(url)
    assert warm.selects == [], "预热后应当全部命中缓存"

    bus = HybridEventBus(backend="memory")
    news_routes.register_cache_invalidation(bus)
    bus.publish(event_name, {"news_ids": []})

    for cache in _ALL_CACHES:
        assert not cache._cache, f"{event_name} 未清空 {cache!r}"

    for url in urls:
        with capture_sql() as after:
            assert client.get(url).status_code == 200
        assert after.selects, f"{url}: 失效后应重新查库"


def test_news_list_cache_reflects_new_rows_after_invalidation(seeded, enabled_caches, client) -> None:
    """列表缓存是本次新增的，必须真的会因为新入库的新闻而失效。"""
    before = client.get("/api/news?limit=200").json()
    assert client.get("/api/news?limit=200").json() == before

    with SessionLocal() as session:
        session.add(
            _make_news(
                "us-3",
                market="us",
                source="Reuters",
                title="Freshly ingested story",
                published_at=_NOW,
            )
        )
        session.commit()

    # 没有事件时，短 TTL 内仍返回旧结果（这是缓存的正常语义）
    assert client.get("/api/news?limit=200").json() == before

    bus = HybridEventBus(backend="memory")
    news_routes.register_cache_invalidation(bus)
    bus.publish("news.created_batch", {"news_ids": []})

    after = client.get("/api/news?limit=200").json()
    titles = {item["title"] for item in after["items"]}
    assert "Freshly ingested story" in titles


# ---------------------------------------------------------------------------
# 5. 列表缓存 key 隔离（最容易写错的地方）
# ---------------------------------------------------------------------------


def test_news_list_cache_key_isolates_market(seeded, enabled_caches, client) -> None:
    us_first = client.get("/api/news?market=us&limit=200").json()
    hk_first = client.get("/api/news?market=hk&limit=200").json()

    assert {item["market"] for item in us_first["items"]} == {"us"}
    assert {item["market"] for item in hk_first["items"]} == {"hk"}

    # 第二轮全部走缓存，绝不能串味
    with capture_sql() as recorder:
        us_second = client.get("/api/news?market=us&limit=200").json()
        hk_second = client.get("/api/news?market=hk&limit=200").json()
    assert recorder.selects == []
    assert us_second == us_first
    assert hk_second == hk_first
    assert us_second != hk_second


def test_news_list_cache_key_isolates_limit(seeded, enabled_caches, client) -> None:
    one = client.get("/api/news?market=us&limit=1").json()
    two = client.get("/api/news?market=us&limit=2").json()
    assert len(one["items"]) == 1
    assert len(two["items"]) == 2

    with capture_sql() as recorder:
        assert client.get("/api/news?market=us&limit=1").json() == one
        assert client.get("/api/news?market=us&limit=2").json() == two
    assert recorder.selects == []


def test_news_list_cache_key_isolates_cursor(seeded, enabled_caches, client) -> None:
    page1 = client.get("/api/news?market=us&limit=1").json()
    cursor = page1["next_cursor"]
    assert cursor, "需要一个非空 cursor 才能验证隔离"

    page2 = client.get(f"/api/news?market=us&limit=1&cursor={cursor}").json()
    assert page2["items"][0]["id"] != page1["items"][0]["id"]

    with capture_sql() as recorder:
        assert client.get("/api/news?market=us&limit=1").json() == page1
        assert client.get(f"/api/news?market=us&limit=1&cursor={cursor}").json() == page2
    assert recorder.selects == []


def test_news_list_cache_key_isolates_source_and_sentiment(seeded, enabled_caches, client) -> None:
    reuters = client.get("/api/news?market=us&source_name=Reuters&limit=200").json()
    bloomberg = client.get("/api/news?market=us&source_name=Bloomberg&limit=200").json()
    unfiltered = client.get("/api/news?market=us&limit=200").json()

    assert {i["source_name"] for i in reuters["items"]} == {"Reuters"}
    assert {i["source_name"] for i in bloomberg["items"]} == {"Bloomberg"}
    assert len(unfiltered["items"]) >= len(reuters["items"]) + len(bloomberg["items"])

    neutral = client.get("/api/news?market=us&sentiment_label=neutral&limit=200").json()

    with capture_sql() as recorder:
        assert client.get("/api/news?market=us&source_name=Reuters&limit=200").json() == reuters
        assert client.get("/api/news?market=us&source_name=Bloomberg&limit=200").json() == bloomberg
        assert client.get("/api/news?market=us&limit=200").json() == unfiltered
        assert client.get("/api/news?market=us&sentiment_label=neutral&limit=200").json() == neutral
    assert recorder.selects == []


def test_feed_layout_cache_key_isolates_params(seeded, enabled_caches, client) -> None:
    a = client.get("/api/news/feed-layout?market=us&limit_stream=5").json()
    b = client.get("/api/news/feed-layout?market=hk&limit_stream=5").json()
    c = client.get("/api/news/feed-layout?market=us&limit_stream=1").json()

    assert len(c["stream"]) <= 1
    with capture_sql() as recorder:
        assert client.get("/api/news/feed-layout?market=us&limit_stream=5").json() == a
        assert client.get("/api/news/feed-layout?market=hk&limit_stream=5").json() == b
        assert client.get("/api/news/feed-layout?market=us&limit_stream=1").json() == c
    assert recorder.selects == []


def test_topics_cache_key_isolates_pagination(seeded, enabled_caches, client) -> None:
    full = client.get("/api/topics").json()
    page = client.get("/api/topics?limit=1&offset=0").json()
    assert len(page) == 1
    assert len(full) >= 1

    with capture_sql() as recorder:
        assert client.get("/api/topics").json() == full
        assert client.get("/api/topics?limit=1&offset=0").json() == page
    assert recorder.selects == []


# ---------------------------------------------------------------------------
# 6. 搜索请求刻意不缓存
# ---------------------------------------------------------------------------


def test_search_requests_bypass_the_list_cache(seeded, enabled_caches, client) -> None:
    """带 q 的请求不入缓存：key 基数由用户控制，会把热点 key 挤出共享 LRU。"""
    news_routes._news_list_cache.clear()

    first = client.get("/api/news?q=NVIDIA&limit=200")
    assert first.status_code == 200
    assert not news_routes._news_list_cache._cache, "搜索请求不应写入缓存"

    with capture_sql() as recorder:
        second = client.get("/api/news?q=NVIDIA&limit=200")
    assert recorder.selects, "搜索请求每次都应查库"
    # 不缓存，但响应内容依旧要正确且稳定
    assert second.json() == first.json()
    assert second.content == first.content


def test_search_key_flood_does_not_evict_hot_list_entries(seeded, enabled_caches, client) -> None:
    """回归：一串随机搜索词不得把前端默认视图的热点 key 挤出缓存。"""
    hot = client.get("/api/news?limit=200")
    assert client.get("/api/news?limit=200").content == hot.content

    for i in range(64):
        client.get(f"/api/news?q=random-term-{i}&limit=200")

    with capture_sql() as recorder:
        again = client.get("/api/news?limit=200")
    assert recorder.selects == [], "热点 key 被搜索请求挤掉了"
    assert again.content == hot.content


def test_list_cache_respects_lru_capacity(seeded, enabled_caches) -> None:
    """key 基数兜底：即便全是可缓存的参数组合，也不会无上限增长。"""
    cache = news_routes._news_list_cache
    cache.clear()
    for i in range(cache.max_entries * 3):
        cache.set((None, None, None, None, None, i), b"{}")
    assert len(cache._cache) == cache.max_entries


# ---------------------------------------------------------------------------
# 7. route_cache_enabled=false 时行为不变
# ---------------------------------------------------------------------------


def test_disabled_caches_always_hit_the_database(seeded, disabled_caches, client) -> None:
    for name, url, _route_path in _endpoints(seeded):
        with capture_sql() as first:
            a = client.get(url)
        with capture_sql() as second:
            b = client.get(url)
        assert a.status_code == b.status_code == 200, name
        assert first.selects, f"{name}: 关闭缓存后第一次请求应查库"
        assert second.selects, f"{name}: 关闭缓存后第二次请求仍应查库"
        assert a.content == b.content, name

    for cache in _ALL_CACHES:
        assert not cache._cache, "缓存关闭时不得写入任何条目"


def test_disabled_cache_still_returns_valid_json_bytes(seeded, disabled_caches, client) -> None:
    """enabled=False 时 store() 的 set 是 no-op，但仍必须返回渲染好的响应体。"""
    response = client.get("/api/topics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert isinstance(payload, list) and payload
    assert {"id", "topic_title", "keywords", "related_symbols"} <= set(payload[0])


def test_event_detail_404_still_not_cached(seeded, enabled_caches, client) -> None:
    response = client.get("/api/news/events/topic-does-not-exist-999")
    assert response.status_code == 404
    assert response.json()["detail"] == "event not found"
    assert news_routes._event_detail_cache.get("topic-does-not-exist-999") is None


# ---------------------------------------------------------------------------
# 8. 缓存实现本身
# ---------------------------------------------------------------------------


def test_json_bytes_cache_keeps_simple_ttl_cache_semantics() -> None:
    """新封装不得改动 get/set/clear/ttl/enabled 的既有语义。"""
    cache = JsonBytesTTLCache(ttl=60.0, enabled=True, max_entries=2)
    assert cache.ttl == 60.0 and cache.enabled is True

    cache.set("a", b'{"x":1}')
    assert cache.get("a") == b'{"x":1}'

    response = cache.cached_response("a")
    assert response is not None
    assert response.body == b'{"x":1}'
    assert response.media_type == "application/json"

    assert cache.cached_response("missing") is None

    cache.clear()
    assert cache.get("a") is None

    cache.enabled = False
    cache.set("b", b"{}")
    assert cache.get("b") is None
    assert cache.cached_response("b") is None


def test_fast_path_matches_jsonable_encoder_path(seeded, enabled_caches, client, monkeypatch) -> None:
    """快路径（pydantic Rust 序列化器）与语义基准（jsonable_encoder + json.dumps）
    必须输出完全相同的字节 —— 这是允许启用快路径的前提。"""
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    from app.core.simple_cache import _fast_json_bytes

    checked = 0
    for name, url, _route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()
        with capture_cached_views(monkeypatch) as captured:
            assert client.get(url).status_code == 200, name
        view = captured[0]

        fast = _fast_json_bytes(view)
        assert fast is not None, f"{name}: 快路径未覆盖到这个形状（会白白回落到慢路径）"
        reference = JSONResponse(content=jsonable_encoder(view)).body
        assert fast == reference, f"{name}: 快路径与 jsonable_encoder 路径字节不一致"
        checked += 1

    assert checked == 6


def test_handler_return_type_matches_declared_response_model(seeded, enabled_caches, client, monkeypatch) -> None:
    """字节缓存成立的前提：handler 构造的对象类型 == response_model 声明的类型。

    如果哪天 handler 返回了 response_model 的**子类**，FastAPI 原生链路会按父类
    裁掉多出来的字段，而字节缓存是按实际对象渲染的 —— 两者就会分叉。这里把这个
    不变量显式钉死，避免以后有人不知不觉踩进去。
    """
    import typing

    for name, url, route_path in _endpoints(seeded):
        for cache in _ALL_CACHES:
            cache.clear()
        with capture_cached_views(monkeypatch) as captured:
            assert client.get(url).status_code == 200, name
        view = captured[0]
        declared = _route_response_model(route_path)

        if typing.get_origin(declared) is list:
            (item_type,) = typing.get_args(declared)
            assert isinstance(view, list), name
            assert all(type(item) is item_type for item in view), name
        else:
            assert type(view) is declared, f"{name}: {type(view)} != {declared}"


def test_fast_path_falls_back_for_unknown_shapes() -> None:
    from app.core.simple_cache import _fast_json_bytes, render_json_bytes

    # 空列表 / 异构列表 / 裸 dict 都认不出形状，必须回落而不是崩掉
    assert _fast_json_bytes([]) is None
    assert _fast_json_bytes({"a": 1}) is None
    assert render_json_bytes([]) == b"[]"
    assert render_json_bytes({"a": 1, "b": None}) == b'{"a":1,"b":null}'


def test_render_json_bytes_matches_json_response_render() -> None:
    from fastapi.responses import JSONResponse

    from app.core.simple_cache import render_json_bytes

    view = TopicItemView(
        id=1,
        topic_title="中文 title",
        display_name=None,
        alias_zh=None,
        topic_summary=None,
        keywords=["a", "b"],
        market="us",
        sentiment_label="neutral",
        importance_score=0.5,
        news_count=0,
        last_seen_at=_NOW,
        related_symbols=[],
    )
    body = render_json_bytes([view])
    assert body == _fastapi_reference_bytes(list[TopicItemView], [view])
    # 与 starlette 自己的 render 参数（compact + ensure_ascii=False）一致
    assert b'"topic_title":"\xe4\xb8\xad\xe6\x96\x87 title"' in body
    assert b'"display_name":null' in body
    assert JSONResponse(content=_bytes_to_json(body)).body == body
