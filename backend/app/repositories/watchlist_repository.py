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
        self.session.flush()
        self.session.refresh(item)
        return item

    def update_position(self, symbol: str, updates: dict[str, float | None]) -> WatchlistItem | None:
        """写入持仓量 / 平均成本（持仓/组合视图）。

        upsert 语义：仅 ``updates`` 中出现的键会被写入（未出现的字段保持原值），
        因此传 ``{"position_size": None}`` 可清空持仓、而不影响 average_cost。
        既有的 alert / display_name 等字段一律不受影响。找不到 symbol 返回 None。
        """
        item = self.get_by_symbol(symbol)
        if item is None:
            return None
        for field in ("position_size", "average_cost"):
            if field in updates:
                setattr(item, field, updates[field])
        self.session.flush()
        self.session.refresh(item)
        return item

    def delete_by_symbol(self, symbol: str) -> bool:
        item = self.get_by_symbol(symbol)
        if item is None:
            return False

        self.session.delete(item)
        self.session.flush()
        return True
