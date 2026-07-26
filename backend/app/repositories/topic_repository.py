from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_repository import news_summary_load_option


class TopicRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, *, limit: int | None = None, offset: int = 0) -> list[TopicCluster]:
        """按 (importance_score, last_seen_at) 降序列出 topic。

        limit/offset 为可选:不传时保持“全量返回”的原有行为(其它调用方依赖),
        feed-layout 这类只要前若干条的调用方必须显式限量,避免每请求把整张
        topic_cluster 拉进内存。索引:ix_topic_cluster_importance_seen。
        """
        stmt = select(TopicCluster).order_by(
            TopicCluster.importance_score.desc(), TopicCluster.last_seen_at.desc()
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        return list(self.session.scalars(stmt))

    def get_by_id(self, topic_id: int) -> TopicCluster | None:
        stmt = select(TopicCluster).where(TopicCluster.id == topic_id)
        return self.session.scalar(stmt)

    def list_news_for_topic(self, topic_id: int) -> list[NewsItem]:
        stmt = (
            select(NewsItem)
            .join(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
            .where(TopicNewsLink.topic_cluster_id == topic_id)
            .options(news_summary_load_option())
            .order_by(NewsItem.published_at.desc(), NewsItem.fetched_at.desc())
        )
        return list(self.session.scalars(stmt))

    def list_related_symbols(self, topic_id: int, market: str | None = None) -> list[str]:
        stmt = (
            select(NewsStockMention.symbol)
            .join(TopicNewsLink, TopicNewsLink.news_id == NewsStockMention.news_id)
            .join(NewsItem, NewsItem.id == NewsStockMention.news_id)
            .where(TopicNewsLink.topic_cluster_id == topic_id)
        )
        if market:
            stmt = stmt.where(NewsItem.market == market, NewsStockMention.market == market)
        stmt = stmt.group_by(NewsStockMention.symbol).order_by(
            func.count(NewsStockMention.symbol).desc(),
            NewsStockMention.symbol.asc(),
        )
        return list(self.session.scalars(stmt))

    def batch_news_for_topics(
        self,
        topic_ids: list[int],
        *,
        market: str | None = None,
    ) -> dict[int, list[NewsItem]]:
        """批量取 topic 关联新闻。

        market 过滤下推到 SQL:此前 feed-layout 在 Python 里筛 market,等于把全市场
        新闻全量 hydrate 之后再丢掉大半。列同样只取 NewsItemSummary 需要的那些。
        """
        if not topic_ids:
            return {}
        stmt = (
            select(TopicNewsLink.topic_cluster_id, NewsItem)
            .join(NewsItem, NewsItem.id == TopicNewsLink.news_id)
            .where(TopicNewsLink.topic_cluster_id.in_(topic_ids))
            .options(news_summary_load_option())
            .order_by(
                TopicNewsLink.topic_cluster_id,
                NewsItem.published_at.desc(),
                NewsItem.fetched_at.desc(),
            )
        )
        if market:
            stmt = stmt.where(NewsItem.market == market)
        result: dict[int, list[NewsItem]] = {tid: [] for tid in topic_ids}
        for topic_id, news_item in self.session.execute(stmt):
            result[topic_id].append(news_item)
        return result

    def batch_related_symbols(
        self, topic_ids: list[int], market: str | None = None
    ) -> dict[int, list[str]]:
        if not topic_ids:
            return {}
        stmt = (
            select(
                TopicNewsLink.topic_cluster_id,
                NewsStockMention.symbol,
                func.count(NewsStockMention.symbol).label("cnt"),
            )
            .join(TopicNewsLink, TopicNewsLink.news_id == NewsStockMention.news_id)
            .join(NewsItem, NewsItem.id == NewsStockMention.news_id)
            .where(TopicNewsLink.topic_cluster_id.in_(topic_ids))
            .group_by(TopicNewsLink.topic_cluster_id, NewsStockMention.symbol)
        )
        if market:
            stmt = stmt.where(NewsItem.market == market, NewsStockMention.market == market)
        raw: dict[int, list[tuple[str, int]]] = {tid: [] for tid in topic_ids}
        for topic_id, symbol, cnt in self.session.execute(stmt):
            raw[topic_id].append((symbol, cnt))
        return {
            tid: [symbol for symbol, _ in sorted(pairs, key=lambda p: (-p[1], p[0]))]
            for tid, pairs in raw.items()
        }
