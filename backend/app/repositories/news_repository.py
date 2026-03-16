from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_recent(self, limit: int = 50) -> list[NewsItem]:
        stmt = select(NewsItem).order_by(NewsItem.fetched_at.desc()).limit(limit)
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
