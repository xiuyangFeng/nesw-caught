"""性能优化批次 A（查询层防退化 + 索引）的等价性与索引证据测试。

覆盖：
1. news_item pending partial index 生效、冗余单列索引（title/published_at/market）移除；
2. /news/runtime 的 per-source / per-market 最新新闻映射与旧“全表物化 + Python 折叠”算法等价；
3. MarketRepository.list_latest / list_latest_by_symbols 退化为“每 symbol 最新一条”后与旧
   Python 折叠结果等价，/market/snapshots 响应结构不变；
4. /topics 消除 N+1（常量查询数）且字段与逐 topic 调用旧仓库方法的结果一致。
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text

from app.db.session import SessionLocal, engine
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.source_health import SourceHealth
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.market_repository import MarketRepository
from app.repositories.topic_repository import TopicRepository
from app.services.event_bus import EventBusStatus
from app.services.news_ingestion import SourceDefinition
from app.services.news_runtime import NewsRuntimeService

_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def _make_news(
    url_hash: str,
    *,
    source: str,
    market: str,
    fetched_at: datetime,
    published_at: datetime | None = None,
    signal_status: str | None = None,
) -> NewsItem:
    return NewsItem(
        source_name=source,
        source_url="https://example.com/rss",
        title=f"title-{url_hash}",
        summary=None,
        canonical_url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        market=market,
        language="en",
        signal_status=signal_status,
        published_at=published_at,
        fetched_at=fetched_at,
        ingest_status="ingested",
    )


def _make_snapshot(symbol: str, *, price: float, fetched_at: datetime, market: str = "us") -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        market=market,
        price=price,
        change_percent=1.0,
        provider_name="perf-fixture",
        quote_status="ok",
        fetched_at=fetched_at,
    )


@pytest.fixture(autouse=True)
def _cleanup_perf_fixtures():
    yield
    with SessionLocal() as session:
        tagged_topic_ids = select(TopicCluster.id).where(TopicCluster.topic_key.like("pba-%"))
        tagged_news_ids = select(NewsItem.id).where(NewsItem.url_hash.like("pba-%"))
        session.execute(delete(TopicNewsLink).where(TopicNewsLink.topic_cluster_id.in_(tagged_topic_ids)))
        session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(tagged_news_ids)))
        session.execute(delete(TopicCluster).where(TopicCluster.topic_key.like("pba-%")))
        session.execute(delete(NewsItem).where(NewsItem.url_hash.like("pba-%")))
        session.execute(delete(PriceSnapshot).where(PriceSnapshot.symbol.like("PBA%")))
        session.execute(delete(SourceHealth).where(SourceHealth.source_name.like("Pba%")))
        session.commit()


# ---------------------------------------------------------------------------
# 1. 索引：partial index 生效 + 冗余单列索引移除
# ---------------------------------------------------------------------------


def test_news_item_pending_partial_index_exists_and_redundant_indexes_dropped() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='news_item'")
        ).all()
    indexes = {row[0]: row[1] for row in rows}
    assert "ix_news_pending" in indexes
    assert "signal_status IS NULL" in indexes["ix_news_pending"]
    # 写放大清理：title 单列索引与前缀重复的 published_at / market 单列索引应已移除
    assert "ix_news_item_title" not in indexes
    assert "ix_news_item_published_at" not in indexes
    assert "ix_news_item_market" not in indexes


def test_list_pending_news_ids_query_plan_uses_partial_index() -> None:
    with SessionLocal() as session:
        for i in range(40):
            session.add(
                _make_news(
                    f"pba-plan-done-{i}",
                    source="PbaPlan",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=i),
                    signal_status="done",
                )
            )
        for i in range(8):
            session.add(
                _make_news(
                    f"pba-plan-pending-{i}",
                    source="PbaPlan",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=i),
                    signal_status=None,
                )
            )
        session.commit()

        plan_rows = session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM news_item WHERE signal_status IS NULL "
                "ORDER BY published_at IS NULL, published_at DESC, fetched_at DESC LIMIT 5"
            )
        ).all()
    plan_detail = " | ".join(str(row[3]) for row in plan_rows)
    assert "ix_news_pending" in plan_detail


def test_price_snapshot_composite_index_exists_and_groupby_plan_uses_it() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='price_snapshot'")
        ).all()
        index_names = {row[0] for row in rows}
        assert "ix_price_snapshot_symbol_fetched" in index_names

        for i in range(30):
            for symbol in ("PBA1", "PBA2", "PBA3"):
                session.add(
                    _make_snapshot(symbol, price=100 + i, fetched_at=_NOW - timedelta(minutes=i))
                )
        session.commit()

        plan_rows = session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT symbol, MAX(fetched_at) FROM price_snapshot "
                "WHERE symbol IN ('PBA1', 'PBA2') GROUP BY symbol"
            )
        ).all()
    plan_detail = " | ".join(str(row[3]) for row in plan_rows)
    assert "ix_price_snapshot_symbol_fetched" in plan_detail


# ---------------------------------------------------------------------------
# 2. /news/runtime：SQL 聚合结果与旧全表物化算法等价
# ---------------------------------------------------------------------------


def _legacy_latest_maps(session, source_keys: set[tuple[str, str]]):
    """旧实现的全表物化 + Python 折叠算法，作为等价性参照。"""
    by_source: dict[tuple[str, str], NewsItem] = {}
    by_market: dict[str, NewsItem] = {}
    stmt = select(NewsItem).order_by(
        NewsItem.market.asc(), NewsItem.fetched_at.desc(), NewsItem.id.desc()
    )
    for row in session.scalars(stmt):
        source_key = (row.source_name, row.market)
        if source_key in source_keys:
            by_source.setdefault(source_key, row)
            by_market.setdefault(row.market, row)
    return by_source, by_market


def _normalize(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def test_news_runtime_latest_maps_match_legacy_full_scan(monkeypatch) -> None:
    monkeypatch.setattr("app.services.news_runtime._utc_now", lambda: _NOW)
    monkeypatch.setattr(
        "app.services.news_runtime.load_sources",
        lambda: [
            SourceDefinition(
                name="PbaUS1", source_type="rss", url="https://example.com/1", market="us", markets=["us"]
            ),
            SourceDefinition(
                name="PbaUS2", source_type="rss", url="https://example.com/2", market="us", markets=["us"]
            ),
            SourceDefinition(
                name="PbaHK1", source_type="rss", url="https://example.com/3", market="hk", markets=["hk"]
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.news_runtime.get_event_bus",
        lambda: type(
            "FakeBus",
            (),
            {
                "get_status": staticmethod(
                    lambda: EventBusStatus(
                        backend="memory",
                        status="ok",
                        redis_enabled=False,
                        last_published_at=None,
                        last_event_name=None,
                    )
                )
            },
        )(),
    )

    with SessionLocal() as session:
        for name, market in (("PbaUS1", "us"), ("PbaUS2", "us"), ("PbaHK1", "hk")):
            session.add(
                SourceHealth(
                    source_name=name,
                    market=market,
                    source_type="rss",
                    last_success_at=_NOW,
                    consecutive_failures=0,
                )
            )
        session.add_all(
            [
                _make_news(
                    "pba-rt-us1-old",
                    source="PbaUS1",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=20),
                    published_at=_NOW - timedelta(minutes=25),
                ),
                # 与 us1-new-b 同一 fetched_at：并列时旧算法按 id DESC 取大 id 的一条
                _make_news(
                    "pba-rt-us1-new-a",
                    source="PbaUS1",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=5),
                    published_at=_NOW - timedelta(minutes=6),
                ),
                _make_news(
                    "pba-rt-us1-new-b",
                    source="PbaUS1",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=5),
                    published_at=_NOW - timedelta(minutes=7),
                ),
                _make_news(
                    "pba-rt-us2",
                    source="PbaUS2",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=3),
                    published_at=_NOW - timedelta(minutes=4),
                ),
                _make_news(
                    "pba-rt-hk1",
                    source="PbaHK1",
                    market="hk",
                    fetched_at=_NOW - timedelta(minutes=2),
                    published_at=None,
                ),
                # 无 source_health 行的“幽灵”源，全表最新但必须被忽略
                _make_news(
                    "pba-rt-ghost",
                    source="PbaGhost",
                    market="us",
                    fetched_at=_NOW - timedelta(minutes=1),
                    published_at=_NOW - timedelta(minutes=1),
                ),
            ]
        )
        session.commit()

        view = NewsRuntimeService(session).build()
        ref_by_source, ref_by_market = _legacy_latest_maps(
            session, {("PbaUS1", "us"), ("PbaUS2", "us"), ("PbaHK1", "hk")}
        )

    # 参照实现 sanity check：幽灵源不应出现在参照里，us 市场最新应是 us2 的新闻
    assert set(ref_by_source) == {("PbaUS1", "us"), ("PbaUS2", "us"), ("PbaHK1", "hk")}
    assert ref_by_source[("PbaUS1", "us")].url_hash == "pba-rt-us1-new-b"
    assert ref_by_market["us"].url_hash == "pba-rt-us2"
    assert ref_by_market["hk"].url_hash == "pba-rt-hk1"

    source_views = {(item.source_name, item.market): item for item in view.sources}
    for key, ref_row in ref_by_source.items():
        item = source_views[key]
        assert item.latest_news_fetched_at == _normalize(ref_row.fetched_at), key
        assert item.latest_news_published_at == _normalize(ref_row.published_at), key

    market_views = {item.market: item for item in view.markets}
    for market, ref_row in ref_by_market.items():
        assert market_views[market].last_news_created_at == _normalize(ref_row.fetched_at), market

    expected_global = max(_normalize(row.fetched_at) for row in ref_by_market.values())
    assert view.last_news_created_at == expected_global
    assert view.feed_status == "delayed"


# ---------------------------------------------------------------------------
# 3. price_snapshot：每 symbol 最新一条，与旧 Python 折叠等价
# ---------------------------------------------------------------------------


def _legacy_latest_by_symbols(session, symbols: list[str]) -> dict[str, PriceSnapshot]:
    """旧 list_latest_by_symbols 实现（拉全历史 Python 取最新），作为等价性参照。"""
    stmt = (
        select(PriceSnapshot)
        .where(PriceSnapshot.symbol.in_(symbols))
        .order_by(PriceSnapshot.symbol, PriceSnapshot.fetched_at.desc())
    )
    latest: dict[str, PriceSnapshot] = {}
    for snapshot in session.scalars(stmt):
        latest.setdefault(snapshot.symbol, snapshot)
    return latest


def _seed_snapshot_history() -> dict[str, int]:
    """每个 symbol 写多条历史，返回 symbol -> 最新行期望 price。"""
    latest_price: dict[str, int] = {}
    with SessionLocal() as session:
        for symbol, base in (("PBA1", 100), ("PBA2", 200), ("PBA3", 300)):
            for i in range(4):
                price = base + i
                session.add(
                    _make_snapshot(symbol, price=price, fetched_at=_NOW - timedelta(minutes=40 - i * 10))
                )
            latest_price[symbol] = base + 3
        session.commit()
    return latest_price


def test_list_latest_by_symbols_matches_legacy_python_fold() -> None:
    _seed_snapshot_history()
    with SessionLocal() as session:
        repository = MarketRepository(session)
        symbols = ["PBA1", "PBA2", "PBA3", "PBA_MISSING"]
        current = repository.list_latest_by_symbols(symbols)
        legacy = _legacy_latest_by_symbols(session, symbols)

        assert set(current) == set(legacy)
        for symbol, legacy_row in legacy.items():
            assert current[symbol].id == legacy_row.id, symbol
            assert current[symbol].fetched_at == legacy_row.fetched_at, symbol
        assert "PBA_MISSING" not in current
        assert repository.list_latest_by_symbols([]) == {}


def test_list_latest_by_symbols_tie_breaks_by_higher_id() -> None:
    with SessionLocal() as session:
        first = _make_snapshot("PBA1", price=100, fetched_at=_NOW)
        session.add(first)
        session.flush()
        second = _make_snapshot("PBA1", price=101, fetched_at=_NOW)
        session.add(second)
        session.commit()
        latest = MarketRepository(session).list_latest_by_symbols(["PBA1"])
        assert latest["PBA1"].id == second.id
        assert latest["PBA1"].price == 101


def test_list_latest_returns_latest_row_per_symbol() -> None:
    latest_price = _seed_snapshot_history()
    with SessionLocal() as session:
        rows = MarketRepository(session).list_latest()
    mine = [row for row in rows if row.symbol.startswith("PBA")]
    assert {row.symbol: row.price for row in mine} == latest_price
    # 全局每 symbol 至多一条
    assert len(rows) == len({row.symbol for row in rows})
    # 保持与旧接口一致的“最新在前”排序
    assert [row.symbol for row in mine] == ["PBA3", "PBA2", "PBA1"]


def test_market_snapshots_route_returns_latest_per_symbol_with_same_shape() -> None:
    latest_price = _seed_snapshot_history()
    client = TestClient(app)
    response = client.get("/api/market/snapshots")
    assert response.status_code == 200
    payload = response.json()
    mine = [item for item in payload if item["symbol"].startswith("PBA")]
    assert {item["symbol"]: item["price"] for item in mine} == latest_price
    assert len(payload) == len({item["symbol"] for item in payload})
    for item in mine:
        assert set(item) == {
            "symbol",
            "market",
            "display_name",
            "provider_symbol",
            "price",
            "change_amount",
            "change_percent",
            "open_price",
            "previous_close",
            "day_high",
            "day_low",
            "volume",
            "status",
            "source",
            "message",
            "is_abnormal",
            "abnormal_reason",
            "has_hot_alert",
            "fetched_at",
        }


def test_list_snapshots_by_symbols_keeps_full_history_asc() -> None:
    _seed_snapshot_history()
    with SessionLocal() as session:
        grouped = MarketRepository(session).list_snapshots_by_symbols(["PBA1", "PBA1", "PBA2"])
    assert set(grouped) == {"PBA1", "PBA2"}
    for rows in grouped.values():
        assert len(rows) == 4
        assert [row.fetched_at for row in rows] == sorted(row.fetched_at for row in rows)


# ---------------------------------------------------------------------------
# 4. /topics：消除 N+1，字段与逐 topic 旧仓库调用一致
# ---------------------------------------------------------------------------


def _seed_topics() -> list[int]:
    with SessionLocal() as session:
        topics = [
            TopicCluster(
                topic_key="pba-topic-1",
                topic_title="PBA Topic One",
                topic_summary="s1",
                keywords="alpha,beta",
                sentiment_score=0.5,
                importance_score=0.9,
                last_seen_at=_NOW,
            ),
            TopicCluster(
                topic_key="pba-topic-2",
                topic_title="PBA Topic Two",
                topic_summary="s2",
                keywords="gamma",
                sentiment_score=-0.5,
                importance_score=0.8,
                last_seen_at=_NOW - timedelta(minutes=1),
            ),
            TopicCluster(
                topic_key="pba-topic-3",
                topic_title="PBA Topic Empty",
                topic_summary=None,
                keywords=None,
                sentiment_score=0.0,
                importance_score=0.7,
                last_seen_at=_NOW - timedelta(minutes=2),
            ),
        ]
        session.add_all(topics)
        session.flush()

        news_items = [
            _make_news(
                "pba-tp-n1",
                source="PbaSrc",
                market="us",
                published_at=_NOW - timedelta(minutes=10),
                fetched_at=_NOW - timedelta(minutes=9),
            ),
            _make_news(
                "pba-tp-n2",
                source="PbaSrc",
                market="us",
                published_at=_NOW - timedelta(minutes=20),
                fetched_at=_NOW - timedelta(minutes=8),
            ),
            _make_news(
                "pba-tp-n3",
                source="PbaSrc",
                market="hk",
                published_at=_NOW - timedelta(minutes=30),
                fetched_at=_NOW - timedelta(minutes=7),
            ),
            _make_news(
                "pba-tp-n4",
                source="PbaSrc",
                market="hk",
                published_at=None,
                fetched_at=_NOW - timedelta(minutes=5),
            ),
        ]
        session.add_all(news_items)
        session.flush()

        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topics[0].id, news_id=news_items[0].id),
                TopicNewsLink(topic_cluster_id=topics[0].id, news_id=news_items[1].id),
                TopicNewsLink(topic_cluster_id=topics[0].id, news_id=news_items[2].id),
                TopicNewsLink(topic_cluster_id=topics[1].id, news_id=news_items[3].id),
            ]
        )
        session.add_all(
            [
                NewsStockMention(news_id=news_items[0].id, symbol="AAPL", market="us"),
                NewsStockMention(news_id=news_items[0].id, symbol="TSLA", market="us"),
                NewsStockMention(news_id=news_items[1].id, symbol="AAPL", market="us"),
                NewsStockMention(news_id=news_items[3].id, symbol="0700.HK", market="hk"),
            ]
        )
        session.commit()
        return [topic.id for topic in topics]


def test_list_topics_constant_query_count_and_matches_per_topic_calls() -> None:
    topic_ids = _seed_topics()

    # 参照：旧路由逐 topic 调用的仓库方法（这两个方法本身不变）
    expected: dict[int, dict[str, object]] = {}
    with SessionLocal() as session:
        repository = TopicRepository(session)
        for topic_id in topic_ids:
            news_items = repository.list_news_for_topic(topic_id)
            expected[topic_id] = {
                "market": news_items[0].market if news_items else "us",
                "news_count": len(news_items),
                "related_symbols": repository.list_related_symbols(topic_id),
            }
    assert expected[topic_ids[0]] == {
        "market": "us",
        "news_count": 3,
        "related_symbols": ["AAPL", "TSLA"],
    }
    assert expected[topic_ids[1]] == {
        "market": "hk",
        "news_count": 1,
        "related_symbols": ["0700.HK"],
    }
    assert expected[topic_ids[2]] == {"market": "us", "news_count": 0, "related_symbols": []}

    statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        client = TestClient(app)
        response = client.get("/api/topics")
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert response.status_code == 200
    # 消除 1 + 2T：topics 列表 + 批量新闻 + 批量 symbols，共 3 条 SELECT
    assert len(statements) <= 3, f"expected batched queries, got {len(statements)}: {statements}"

    payload = response.json()
    mine = {item["id"]: item for item in payload if item["id"] in set(topic_ids)}
    assert set(mine) == set(topic_ids)
    for topic_id, fields in expected.items():
        item = mine[topic_id]
        assert item["market"] == fields["market"], topic_id
        assert item["news_count"] == fields["news_count"], topic_id
        assert item["related_symbols"] == fields["related_symbols"], topic_id
    assert mine[topic_ids[0]]["sentiment_label"] == "positive"
    assert mine[topic_ids[1]]["sentiment_label"] == "negative"
