"""NewsSignalRepository.find_topic 批内候选预载测试。

性能背景:关键词兜底原先对每条待分类新闻都 `select(TopicCluster)` 全表载入,
批内 N 条新闻即 N 次全表查询。改为每个 repository 实例(= 每批)只载入一次,
create_topic 后的新 topic 同步纳入候选,匹配语义保持不变。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
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
