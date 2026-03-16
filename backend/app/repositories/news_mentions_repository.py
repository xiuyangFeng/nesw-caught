from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention


class NewsMentionsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_related_news(self, symbol: str) -> list[NewsItem]:
        stmt = (
            select(NewsItem)
            .join(NewsStockMention, NewsStockMention.news_id == NewsItem.id)
            .where(NewsStockMention.symbol == symbol.upper())
            .order_by(NewsItem.published_at.desc(), NewsItem.fetched_at.desc())
        )
        return list(self.session.scalars(stmt))
