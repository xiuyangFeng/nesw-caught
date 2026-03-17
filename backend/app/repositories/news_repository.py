from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink


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

        stmt = stmt.order_by(
            NewsItem.published_at.is_(None).asc(),
            NewsItem.published_at.desc(),
            NewsItem.fetched_at.desc(),
        ).limit(limit)
        return list(self.session.scalars(stmt))

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
