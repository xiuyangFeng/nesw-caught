from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.market_base import MarketBase


class DailyBar(MarketBase):
    __tablename__ = "daily_bar"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    open: Mapped[float] = mapped_column(Float())
    high: Mapped[float] = mapped_column(Float())
    low: Mapped[float] = mapped_column(Float())
    close: Mapped[float] = mapped_column(Float())
    volume: Mapped[float] = mapped_column(Float())
    amount: Mapped[float] = mapped_column(Float())
    turnover_rate: Mapped[float | None] = mapped_column(Float(), default=None)


class IndexDailyBar(MarketBase):
    __tablename__ = "index_daily_bar"

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    open: Mapped[float] = mapped_column(Float())
    high: Mapped[float] = mapped_column(Float())
    low: Mapped[float] = mapped_column(Float())
    close: Mapped[float] = mapped_column(Float())
    volume: Mapped[float] = mapped_column(Float())
    amount: Mapped[float] = mapped_column(Float())


class TradeCalendar(MarketBase):
    __tablename__ = "trade_calendar"

    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    is_open: Mapped[int] = mapped_column(Integer(), default=1)


class FundFlowDaily(MarketBase):
    __tablename__ = "fund_flow_daily"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    main_net_inflow: Mapped[float | None] = mapped_column(Float(), default=None)
    super_large_net: Mapped[float | None] = mapped_column(Float(), default=None)
    large_net: Mapped[float | None] = mapped_column(Float(), default=None)
    medium_net: Mapped[float | None] = mapped_column(Float(), default=None)
    small_net: Mapped[float | None] = mapped_column(Float(), default=None)
    main_net_pct: Mapped[float | None] = mapped_column(Float(), default=None)
