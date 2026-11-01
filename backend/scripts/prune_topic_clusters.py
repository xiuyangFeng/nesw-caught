"""存量伪事件清理脚本（2026-11-01）。

背景
----
旧聚类规则把无关键词的新闻全部落进兜底事件 ``general-market-update``（实测
1,894 条），并靠 "stock / just / why / non / gaap / eps / beats" 等通用词把无关
新闻串成巨型伪事件（"supermicro stock just" 886 条里只有 1 条提到 Supermicro）。
新规则见 ``app/services/topic_matching.py``，只管新入库的新闻；本脚本清理存量。

做什么
------
1. 删除 key 不可聚类的事件（兜底 key、通用词/数字打头的 key）及其关联；
2. 其余事件里，标题+摘要都不含事件主体（第一个有效关键词）的成员解除关联；
   成员清空的事件一并删除；
3. 对剩余被改动的事件刷新统计字段。

新闻本身不删，只解除"新闻 ↔ 事件"关联。默认 dry-run，加 ``--apply`` 才写库；
幂等，重复运行第二次无改动。运行前请先备份 ``backend/data/app.db``。

用法::

    cd backend && python -m scripts.prune_topic_clusters            # 只看统计
    cd backend && python -m scripts.prune_topic_clusters --apply    # 执行
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_signal_repository import NewsSignalRepository
from app.services.topic_matching import is_clusterable_topic_key, meaningful_keywords


@dataclass
class PruneReport:
    deleted_topics: int = 0
    pruned_links: int = 0
    emptied_topics: int = 0
    samples: list[str] = field(default_factory=list)


def _topic_entity(topic: TopicCluster) -> str | None:
    keywords = meaningful_keywords((topic.keywords or "").split(","))
    if keywords:
        return keywords[0]
    key_terms = meaningful_keywords((topic.topic_key or "").replace("-", " ").split())
    return key_terms[0] if key_terms else None


def prune_topic_clusters(session: Session, *, apply: bool) -> PruneReport:
    report = PruneReport()
    # topic_key 为空的事件不是分类器建的（种子/手工数据），不归本脚本管。
    topics = list(session.scalars(select(TopicCluster).where(TopicCluster.topic_key.is_not(None))))

    drop_topic_ids = {topic.id for topic in topics if not is_clusterable_topic_key(topic.topic_key)}
    report.deleted_topics = len(drop_topic_ids)
    report.samples.extend(
        f"删除事件 {topic.topic_key!r}" for topic in topics if topic.id in drop_topic_ids
    )

    entities = {topic.id: _topic_entity(topic) for topic in topics if topic.id not in drop_topic_ids}
    rows = session.execute(
        select(TopicNewsLink.id, TopicNewsLink.topic_cluster_id, NewsItem.title, NewsItem.summary).join(
            NewsItem, NewsItem.id == TopicNewsLink.news_id
        )
    ).all()

    prune_link_ids: list[int] = []
    remaining_by_topic: dict[int, int] = defaultdict(int)
    touched_topic_ids: set[int] = set()
    for link_id, topic_id, title, summary in rows:
        if topic_id in drop_topic_ids or topic_id not in entities:
            continue
        entity = entities.get(topic_id)
        text = f"{title or ''} {summary or ''}".lower()
        if entity and entity not in text:
            prune_link_ids.append(link_id)
            touched_topic_ids.add(topic_id)
        else:
            remaining_by_topic[topic_id] += 1
    report.pruned_links = len(prune_link_ids)

    emptied = {topic_id for topic_id in touched_topic_ids if remaining_by_topic[topic_id] == 0}
    report.emptied_topics = len(emptied)

    if not apply:
        return report

    if drop_topic_ids or emptied:
        doomed = drop_topic_ids | emptied
        session.execute(delete(TopicNewsLink).where(TopicNewsLink.topic_cluster_id.in_(doomed)))
        session.execute(delete(TopicCluster).where(TopicCluster.id.in_(doomed)))
    for start in range(0, len(prune_link_ids), 500):
        chunk = prune_link_ids[start : start + 500]
        session.execute(delete(TopicNewsLink).where(TopicNewsLink.id.in_(chunk)))
    NewsSignalRepository(session).refresh_topic_stats(touched_topic_ids - emptied)
    session.commit()
    return report


def _build_session_factory(database_url: str | None):
    if not database_url:
        from app.db.session import SessionLocal

        return SessionLocal
    connect_args = {"timeout": 30, "check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清理存量伪事件（兜底事件 + 通用词串起来的巨型事件）")
    parser.add_argument("--apply", action="store_true", help="真正写库；默认只打印统计")
    parser.add_argument("--database-url", default=None, help="默认读 Settings.database_url")
    args = parser.parse_args(argv)

    with _build_session_factory(args.database_url)() as session:
        report = prune_topic_clusters(session, apply=args.apply)
    mode = "apply" if args.apply else "dry-run"
    print(
        f"[{mode}] 删除不可聚类事件 {report.deleted_topics} 个；"
        f"解除无关成员 {report.pruned_links} 条；因此清空的事件 {report.emptied_topics} 个"
    )
    for line in report.samples[:10]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
