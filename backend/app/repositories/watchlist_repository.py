from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.watchlist_item import WatchlistItem


class WatchlistRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[WatchlistItem]:
        stmt = select(WatchlistItem).order_by(WatchlistItem.market, WatchlistItem.symbol)
        return list(self.session.scalars(stmt))

    def get_by_symbol(self, symbol: str) -> WatchlistItem | None:
        stmt = select(WatchlistItem).where(WatchlistItem.symbol == symbol.upper())
        return self.session.scalar(stmt)

    def create(self, *, symbol: str, market: str, display_name: str, alert_threshold: float | None, alert_mode: str) -> WatchlistItem:
        item = WatchlistItem(
            symbol=symbol.upper(),
            market=market,
            display_name=display_name,
            is_active=True,
            alert_threshold=alert_threshold,
            alert_mode=alert_mode,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item
