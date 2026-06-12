from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_cursor import decode_cursor, encode_cursor


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
            keyword = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(NewsItem.title).like(keyword),
                    func.lower(func.coalesce(NewsItem.summary, "")).like(keyword),
                )
            )

        if cursor:
            cursor_published_at, cursor_id = decode_cursor(cursor)
            if cursor_published_at is None:
                stmt = stmt.where(
                    NewsItem.published_at.is_(None),
                    NewsItem.id < cursor_id,
                )
            else:
                stmt = stmt.where(
                    or_(
                        NewsItem.published_at.is_(None),
                        NewsItem.published_at < cursor_published_at,
                        and_(
                            NewsItem.published_at == cursor_published_at,
                            NewsItem.id < cursor_id,
                        ),
                    )
                )

        stmt = stmt.order_by(
            NewsItem.published_at.is_(None).asc(),
            NewsItem.published_at.desc(),
            NewsItem.id.desc(),
        ).limit(limit + 1)
        rows = list(self.session.scalars(stmt))
        has_more = len(rows) > limit
        items = rows[:limit]
        if not has_more or not items:
            return items, None

        last = items[-1]
        return items, encode_cursor(published_at=last.published_at, item_id=last.id)

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

    def get_by_ids(self, news_ids: list[int]) -> list[NewsItem]:
        if not news_ids:
            return []
        stmt = select(NewsItem).where(NewsItem.id.in_(news_ids))
        return list(self.session.scalars(stmt))
