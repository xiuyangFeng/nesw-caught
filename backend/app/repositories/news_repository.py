from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_cursor import decode_cursor, encode_cursor


@dataclass(frozen=True)
class NewsDetailBundle:
    item: NewsItem
    article: ArticleContent | None
    mentions: list[NewsStockMention]
    topic: TopicCluster | None


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_recent(
        self,
        *,
        limit: int = 50,
        market: str | None = None,
        source_name: str | None = None,
        sentiment_label: str | None = None,
        query: str | None = None,
    ) -> list[NewsItem]:
        items, _ = self.list_recent_page(
            limit=limit,
            market=market,
            source_name=source_name,
            sentiment_label=sentiment_label,
            query=query,
        )
        return items

    def list_recent_page(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        market: str | None = None,
        source_name: str | None = None,
        sentiment_label: str | None = None,
        query: str | None = None,
    ) -> tuple[list[NewsItem], str | None]:
        stmt = select(NewsItem)

        if market:
            stmt = stmt.where(NewsItem.market == market)

        if source_name:
            stmt = stmt.where(NewsItem.source_name == source_name)

        if sentiment_label:
            stmt = stmt.where(NewsItem.sentiment_label == sentiment_label)

        if query:
            safe_query = " ".join([w for w in query.strip().split() if w])
            if safe_query:
                try:
                    # Probe with LIMIT 1 to keep the LIKE fallback when FTS has no hits
                    # (e.g. tokenizer misses CJK terms), without pulling all rowids into Python.
                    probe_stmt = text("SELECT rowid FROM news_fts WHERE news_fts MATCH :q LIMIT 1").bindparams(
                        q=safe_query
                    )
                    has_fts_hit = self.session.execute(probe_stmt).first() is not None
                    if has_fts_hit:
                        # Filter via a SQL-level subquery so SQLite resolves the FTS match
                        # itself instead of materializing every rowid into an IN clause.
                        fts_subquery = text("SELECT rowid FROM news_fts WHERE news_fts MATCH :q").bindparams(
                            q=safe_query
                        )
                        stmt = stmt.where(NewsItem.id.in_(fts_subquery))
                    else:
                        keyword = f"%{query.strip().lower()}%"
                        stmt = stmt.where(
                            or_(
                                func.lower(NewsItem.title).like(keyword),
                                func.lower(func.coalesce(NewsItem.summary, "")).like(keyword),
                            )
                        )
                except Exception:
                    keyword = f"%{query.strip().lower()}%"
                    stmt = stmt.where(
                        or_(
                            func.lower(NewsItem.title).like(keyword),
                            func.lower(func.coalesce(NewsItem.summary, "")).like(keyword),
                        )
                    )

        if cursor:
            cursor_effective_at, cursor_id = decode_cursor(cursor)
            if cursor_effective_at is None:
                stmt = stmt.where(NewsItem.id < cursor_id)
            else:
                stmt = stmt.where(
                    or_(
                        NewsItem.effective_at < cursor_effective_at,
                        and_(
                            NewsItem.effective_at == cursor_effective_at,
                            NewsItem.id < cursor_id,
                        ),
                    )
                )

        # Sort by effective_at (= published_at ?? fetched_at) so Chinese feeds
        # without publish time no longer sink. Index: ix_news_effective_id /
        # ix_news_market_effective_id.
        stmt = stmt.order_by(
            NewsItem.effective_at.desc(),
            NewsItem.id.desc(),
        ).limit(limit + 1)
        rows = list(self.session.scalars(stmt))
        has_more = len(rows) > limit
        items = rows[:limit]
        if not has_more or not items:
            return items, None

        last = items[-1]
        return items, encode_cursor(effective_at=last.effective_at, item_id=last.id)

    def get_by_id(self, news_id: int) -> NewsItem | None:
        stmt = select(NewsItem).where(NewsItem.id == news_id)
        return self.session.scalar(stmt)

    def get_article(self, news_id: int) -> ArticleContent | None:
        stmt = select(ArticleContent).where(ArticleContent.news_id == news_id)
        return self.session.scalar(stmt)

    def list_mentions(self, news_id: int) -> list[NewsStockMention]:
        stmt = select(NewsStockMention).where(NewsStockMention.news_id == news_id)
        return list(self.session.scalars(stmt))

    def get_topic_for_news(self, news_id: int) -> TopicCluster | None:
        stmt = (
            select(TopicCluster)
            .join(TopicNewsLink, TopicNewsLink.topic_cluster_id == TopicCluster.id)
            .where(TopicNewsLink.news_id == news_id)
        )
        return self.session.scalar(stmt)

    def get_detail_bundle(self, news_id: int) -> NewsDetailBundle | None:
        """详情页聚合读取:item/article/topic 单条 JOIN 查询 + mentions 一次列表查询。

        原实现为 4 次串行查询,SQLite 单 writer 场景下往返次数直接决定
        抽屉打开延迟,故合并为 2 次。
        """
        stmt = (
            select(NewsItem, ArticleContent, TopicCluster)
            .outerjoin(ArticleContent, ArticleContent.news_id == NewsItem.id)
            .outerjoin(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
            .outerjoin(TopicCluster, TopicCluster.id == TopicNewsLink.topic_cluster_id)
            .where(NewsItem.id == news_id)
        )
        row = self.session.execute(stmt).first()
        if row is None:
            return None
        item, article, topic = row
        return NewsDetailBundle(
            item=item,
            article=article,
            mentions=self.list_mentions(news_id),
            topic=topic,
        )

    def get_by_ids(self, news_ids: list[int]) -> list[NewsItem]:
        if not news_ids:
            return []
        stmt = select(NewsItem).where(NewsItem.id.in_(news_ids))
        return list(self.session.scalars(stmt))
