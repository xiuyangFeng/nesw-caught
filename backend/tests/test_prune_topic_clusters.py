"""backend/scripts/prune_topic_clusters.py 的回归测试（存量伪事件清理）。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from scripts.prune_topic_clusters import main, prune_topic_clusters

T0 = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)


@pytest.fixture()
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'prune.db'}"
    engine = create_engine(url, future=True)
    for model in (NewsItem, TopicCluster, TopicNewsLink):
        model.__table__.create(engine)
    engine.dispose()
    return url


@pytest.fixture()
def session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    engine.dispose()


def _news(session: Session, title: str, summary: str | None = None) -> int:
    item = NewsItem(
        source_name="demo",
        source_url="https://example.com/feed",
        title=title,
        summary=summary,
        canonical_url=f"https://example.com/{title}",
        url_hash=title,
        market="us",
        published_at=T0,
        fetched_at=T0,
        sentiment_score=0.0,
    )
    session.add(item)
    session.flush()
    return item.id


def _topic(session: Session, key: str, keywords: str, news_ids: list[int]) -> int:
    topic = TopicCluster(
        topic_key=key,
        topic_title=key or "手工事件",
        keywords=keywords,
        sentiment_score=0.0,
        importance_score=0.0,
        cluster_version=1,
        last_seen_at=T0,
    )
    session.add(topic)
    session.flush()
    for news_id in news_ids:
        session.add(TopicNewsLink(topic_cluster_id=topic.id, news_id=news_id))
    session.flush()
    return topic.id


def _seed(session_factory) -> dict[str, int]:
    with session_factory() as session:
        wuliangye = _news(session, "五粮液称将持续加大分红力度")
        smci_1 = _news(session, "Supermicro stock just jumped. Here's why")
        smci_2 = _news(session, "Why Supermicro shares are passing peers", "Supermicro rallies")
        pfizer = _news(session, "Pfizer Non-GAAP EPS of $0.77 beats by $0.09")
        chip = _news(session, "半导体板块午后拉升")
        ids = {
            "fallback": _topic(session, "general-market-update", "", [wuliangye]),
            "generic": _topic(session, "should you forget", "should,you,forget,spacex", [pfizer]),
            "smci": _topic(session, "supermicro stock just", "supermicro,stock,just,jumped", [smci_1, smci_2, pfizer]),
            "chip": _topic(session, "半导体", "半导体", [chip]),
            # 非分类器创建的事件（topic_key 为空）不归本脚本管
            "manual": _topic(session, None, "", [chip]),
            "pfizer_news": pfizer,
        }
        session.commit()
        return ids


def test_dry_run_reports_without_writing(session_factory) -> None:
    _seed(session_factory)
    with session_factory() as session:
        report = prune_topic_clusters(session, apply=False)
    assert report.deleted_topics == 2  # 兜底 + 通用词打头
    assert report.pruned_links == 1  # supermicro 事件里的 Pfizer
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TopicCluster)) == 5
        assert session.scalar(select(func.count()).select_from(TopicNewsLink)) == 7


def test_apply_drops_fake_topics_and_unrelated_members(session_factory) -> None:
    ids = _seed(session_factory)
    with session_factory() as session:
        prune_topic_clusters(session, apply=True)

    with session_factory() as session:
        remaining = set(session.scalars(select(TopicCluster.id)))
        assert remaining == {ids["smci"], ids["chip"], ids["manual"]}
        smci_news = set(
            session.scalars(select(TopicNewsLink.news_id).where(TopicNewsLink.topic_cluster_id == ids["smci"]))
        )
        assert ids["pfizer_news"] not in smci_news
        assert len(smci_news) == 2
        # 新闻本身不删
        assert session.scalar(select(func.count()).select_from(NewsItem)) == 5

    # 幂等：再跑一次无事可做
    with session_factory() as session:
        again = prune_topic_clusters(session, apply=True)
    assert again.deleted_topics == 0 and again.pruned_links == 0


def test_main_defaults_to_dry_run(db_url: str, session_factory, capsys) -> None:
    _seed(session_factory)
    assert main(["--database-url", db_url]) == 0
    assert "dry-run" in capsys.readouterr().out
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TopicCluster)) == 5
