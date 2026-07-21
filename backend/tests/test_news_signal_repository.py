"""NewsSignalRepository.find_topic 批内候选预载测试。

性能背景:关键词兜底原先对每条待分类新闻都 `select(TopicCluster)` 全表载入,
批内 N 条新闻即 N 次全表查询。改为每个 repository 实例(= 每批)只载入一次,
create_topic 后的新 topic 同步纳入候选,匹配语义保持不变。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import fmean
from unittest.mock import patch

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_signal_repository import NewsSignalRepository


@pytest.fixture(autouse=True)
def _clean_topics():
    with SessionLocal() as session:
        session.query(TopicNewsLink).delete()
        session.query(TopicCluster).delete()
        session.commit()
    yield


def _seed_topic(session: Session, *, topic_key: str, keywords: str) -> TopicCluster:
    topic = TopicCluster(
        topic_key=topic_key,
        topic_title=topic_key.title(),
        keywords=keywords,
        sentiment_score=0.0,
        importance_score=0.0,
        cluster_version=1,
        last_seen_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    session.add(topic)
    session.commit()
    return topic


def test_find_topic_loads_candidates_once_per_repository() -> None:
    with SessionLocal() as session:
        _seed_topic(session, topic_key="repo cache ai", keywords="ai,cloud,chip")
        _seed_topic(session, topic_key="repo cache oil", keywords="oil,energy")
        repo = NewsSignalRepository(session)

        with patch.object(session, "scalars", wraps=session.scalars) as scalars_spy:
            first = repo.find_topic(topic_key="missing one", keywords=["ai", "cloud"])
            second = repo.find_topic(topic_key="missing two", keywords=["oil", "energy"])

        assert first is not None and first.topic_key == "repo cache ai"
        assert second is not None and second.topic_key == "repo cache oil"
        # 关键词兜底的全表载入每个 repository 实例只发生一次(此前每条新闻一次)。
        assert scalars_spy.call_count == 1


def test_find_topic_candidate_cache_includes_topics_created_within_batch() -> None:
    with SessionLocal() as session:
        _seed_topic(session, topic_key="repo cache base", keywords="macro,rates")
        repo = NewsSignalRepository(session)

        # 首次兜底触发候选载入;新 topic 尚不存在。
        assert repo.find_topic(topic_key="missing", keywords=["ai", "chip"]) is None

        created = repo.create_topic(
            topic_key="repo cache new",
            topic_title="Repo Cache New",
            topic_summary=None,
            keywords=["ai", "chip"],
            last_seen_at=datetime(2026, 7, 17, tzinfo=UTC),
        )

        # 新 topic 必须纳入批内候选:下一条同关键词新闻命中它而不是再建一个。
        found = repo.find_topic(topic_key="another missing", keywords=["ai", "chip"])
        assert found is not None
        assert found.id == created.id


def test_find_topic_keyword_overlap_semantics_unchanged() -> None:
    with SessionLocal() as session:
        _seed_topic(session, topic_key="repo cache sem", keywords="ai,cloud,chip")
        repo = NewsSignalRepository(session)

        # overlap=1 < min(2, 2) => 不命中
        assert repo.find_topic(topic_key="m1", keywords=["ai", "nvidia"]) is None
        # 单词关键词:min(2,1)=1 => overlap 1 命中
        matched = repo.find_topic(topic_key="m2", keywords=["ai"])
        assert matched is not None and matched.topic_key == "repo cache sem"
        # 空关键词 => None
        assert repo.find_topic(topic_key="m3", keywords=[]) is None


# ---------------------------------------------------------------------------
# refresh_topic_stats:批量化后与旧逐 topic 循环实现的等价性 + 查询数常量级测试
# ---------------------------------------------------------------------------


def _make_news_item(
    session: Session,
    *,
    suffix: str,
    sentiment_score: float | None,
    published_at: datetime | None,
    fetched_at: datetime,
) -> NewsItem:
    item = NewsItem(
        source_name="StatsTest",
        source_url="https://example.com/rss",
        title=f"stats {suffix}",
        canonical_url=f"https://example.com/stats-{suffix}",
        url_hash=f"hash-stats-{suffix}",
        market="us",
        sentiment_score=sentiment_score,
        published_at=published_at,
        fetched_at=fetched_at,
    )
    session.add(item)
    session.flush()
    return item


def _legacy_expected_stats(session: Session, topic_ids: set[int]) -> dict[int, dict[str, object]]:
    """旧的逐 topic 循环算法(只读、不落库),作为批量化后的等价性参照。"""
    expected: dict[int, dict[str, object]] = {}
    for topic_id in topic_ids:
        topic = session.scalar(select(TopicCluster).where(TopicCluster.id == topic_id))
        if topic is None:
            continue
        news_items = list(
            session.scalars(
                select(NewsItem)
                .join(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
                .where(TopicNewsLink.topic_cluster_id == topic_id)
            )
        )
        if not news_items:
            continue
        scores = [item.sentiment_score for item in news_items if item.sentiment_score is not None]
        sentiment_score = round(fmean(scores), 4) if scores else 0.0
        last_seen_at = max((item.published_at or item.fetched_at) for item in news_items)
        importance_score = round(
            min(1.0, 0.35 + len(news_items) * 0.15 + min(abs(sentiment_score or 0.0), 0.4)),
            4,
        )
        expected[topic_id] = {
            "sentiment_score": sentiment_score,
            "last_seen_at": last_seen_at,
            "importance_score": importance_score,
        }
    return expected


def test_refresh_topic_stats_matches_legacy_per_topic_loop() -> None:
    with SessionLocal() as session:
        topic_a = TopicCluster(
            topic_key="rts-a", topic_title="Rts A", keywords="a",
            sentiment_score=0.0, importance_score=0.0, cluster_version=1,
        )
        topic_b = TopicCluster(
            topic_key="rts-b", topic_title="Rts B", keywords="b",
            sentiment_score=0.0, importance_score=0.0, cluster_version=1,
        )
        topic_empty = TopicCluster(
            topic_key="rts-empty", topic_title="Rts Empty", keywords="e",
            sentiment_score=0.0, importance_score=0.0, cluster_version=1,
        )
        session.add_all([topic_a, topic_b, topic_empty])
        session.flush()

        base = datetime(2026, 7, 1, tzinfo=UTC)
        n1 = _make_news_item(session, suffix="a1", sentiment_score=0.5, published_at=base, fetched_at=base)
        n2 = _make_news_item(
            session, suffix="a2", sentiment_score=-0.1, published_at=None, fetched_at=base + timedelta(hours=2)
        )
        n3 = _make_news_item(
            session, suffix="b1", sentiment_score=None,
            published_at=base + timedelta(hours=1), fetched_at=base + timedelta(hours=1),
        )
        n4 = _make_news_item(
            session, suffix="b2", sentiment_score=0.3,
            published_at=base + timedelta(hours=3), fetched_at=base + timedelta(hours=3),
        )
        n5 = _make_news_item(
            session, suffix="b3", sentiment_score=0.9, published_at=None, fetched_at=base + timedelta(hours=5)
        )

        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topic_a.id, news_id=n1.id),
                TopicNewsLink(topic_cluster_id=topic_a.id, news_id=n2.id),
                TopicNewsLink(topic_cluster_id=topic_b.id, news_id=n3.id),
                TopicNewsLink(topic_cluster_id=topic_b.id, news_id=n4.id),
                TopicNewsLink(topic_cluster_id=topic_b.id, news_id=n5.id),
            ]
        )
        session.commit()

        # 混入一个不存在的 topic id,验证批量实现与旧实现一样静默跳过。
        missing_topic_id = 1_000_000_000
        topic_ids = {topic_a.id, topic_b.id, topic_empty.id, missing_topic_id}
        expected = _legacy_expected_stats(session, topic_ids)

        repo = NewsSignalRepository(session)
        repo.refresh_topic_stats(topic_ids)
        session.commit()

        session.refresh(topic_a)
        session.refresh(topic_b)
        session.refresh(topic_empty)

        assert topic_a.sentiment_score == expected[topic_a.id]["sentiment_score"]
        assert topic_a.last_seen_at == expected[topic_a.id]["last_seen_at"]
        assert topic_a.importance_score == expected[topic_a.id]["importance_score"]

        assert topic_b.sentiment_score == expected[topic_b.id]["sentiment_score"]
        assert topic_b.last_seen_at == expected[topic_b.id]["last_seen_at"]
        assert topic_b.importance_score == expected[topic_b.id]["importance_score"]

        # 无关联新闻的 topic 不落入 expected,批量实现也应跳过、保持原值不变。
        assert topic_empty.id not in expected
        assert topic_empty.sentiment_score == 0.0
        assert topic_empty.importance_score == 0.0


def test_refresh_topic_stats_uses_constant_query_count() -> None:
    with SessionLocal() as session:
        base = datetime(2026, 7, 2, tzinfo=UTC)
        topic_ids: set[int] = set()
        for i in range(5):
            topic = TopicCluster(
                topic_key=f"rts-cnt-{i}", topic_title=f"Rts Cnt {i}", keywords="x",
                sentiment_score=0.0, importance_score=0.0, cluster_version=1,
            )
            session.add(topic)
            session.flush()
            news = _make_news_item(
                session, suffix=f"cnt-{i}", sentiment_score=0.1 * i, published_at=base, fetched_at=base
            )
            session.add(TopicNewsLink(topic_cluster_id=topic.id, news_id=news.id))
            topic_ids.add(topic.id)
        session.commit()

        repo = NewsSignalRepository(session)

        statements: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", _capture)
        try:
            repo.refresh_topic_stats(topic_ids)
        finally:
            event.remove(engine, "before_cursor_execute", _capture)

        # 旧实现是 O(topics)*2 次查询(5 个 topic => 10 条 SELECT);批量实现应为常量级。
        assert len(statements) <= 2, f"expected batched queries, got {len(statements)}: {statements}"


def test_refresh_topic_stats_noop_for_empty_topic_ids() -> None:
    with SessionLocal() as session:
        repo = NewsSignalRepository(session)
        # 空集合不应触发任何查询或异常。
        repo.refresh_topic_stats(set())
