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

    def list_mentions_for_news(self, news_ids: list[int]) -> list[NewsStockMention]:
        """按 news_id 批量取股票映射（只读，供回测按 news x symbol 展开）。"""
        if not news_ids:
            return []
        stmt = (
            select(NewsStockMention)
            .where(NewsStockMention.news_id.in_(news_ids))
            .order_by(NewsStockMention.news_id.asc(), NewsStockMention.id.asc())
        )
        return list(self.session.scalars(stmt))
