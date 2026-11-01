"""AI 判断用的"我的盘面"上下文：持仓、只关注的股票、关注板块。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.watchlist_item import WatchlistItem
from app.services.ai.sectors import list_focus_sectors


@dataclass(frozen=True)
class WatchStock:
    symbol: str
    market: str
    name: str
    is_holding: bool
    position_size: float | None = None
    average_cost: float | None = None

    @property
    def code_digits(self) -> str:
        return "".join(ch for ch in self.symbol if ch.isdigit())


@dataclass(frozen=True)
class PortfolioContext:
    stocks: tuple[WatchStock, ...]
    focus_sectors: tuple[str, ...]

    @property
    def holdings(self) -> list[WatchStock]:
        return [stock for stock in self.stocks if stock.is_holding]

    @property
    def watch_only(self) -> list[WatchStock]:
        return [stock for stock in self.stocks if not stock.is_holding]

    def find_stock(self, code: str | None, name: str | None) -> WatchStock | None:
        """按代码（容忍有无 .SH/.SZ 后缀、港股前导 0）或名称匹配自选股。"""
        code_text = (code or "").strip().upper()
        digits = "".join(ch for ch in code_text if ch.isdigit())
        for stock in self.stocks:
            if code_text and code_text == stock.symbol.upper():
                return stock
            if digits and stock.code_digits and digits.lstrip("0") == stock.code_digits.lstrip("0"):
                return stock
            if code_text and not digits and code_text == stock.symbol.upper().split(".")[0]:
                return stock
        name_text = (name or "").strip()
        if name_text:
            for stock in self.stocks:
                if name_text == stock.name or name_text.lower() == stock.name.lower():
                    return stock
        return None

    def prompt_block(self) -> str:
        def fmt(stocks: list[WatchStock]) -> str:
            return "、".join(f"{stock.name}({stock.symbol})" for stock in stocks) or "无"

        sectors = "、".join(self.focus_sectors) or "无"
        return f"持仓：{fmt(self.holdings)}\n只关注（未持仓）：{fmt(self.watch_only)}\n关注板块：{sectors}"


def load_portfolio_context(session: Session) -> PortfolioContext:
    stocks = tuple(
        WatchStock(
            symbol=item.symbol.upper(),
            market=item.market,
            name=(item.display_name or item.symbol).strip(),
            is_holding=bool(item.position_size and item.position_size > 0),
            position_size=item.position_size,
            average_cost=item.average_cost,
        )
        for item in session.scalars(
            select(WatchlistItem).where(WatchlistItem.is_active.is_(True)).order_by(WatchlistItem.id)
        )
    )
    return PortfolioContext(stocks=stocks, focus_sectors=tuple(sector.name for sector in list_focus_sectors(session)))
