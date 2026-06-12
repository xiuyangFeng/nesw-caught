from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


QuoteStatus = Literal["ok", "delayed", "unavailable", "symbol_not_supported", "fetch_failed"]


class QuoteSummaryView(BaseModel):
    symbol: str
    market: str
    display_name: str | None = None
    provider_symbol: str | None = None
    price: float | None = None
    change_amount: float | None = None
    change_percent: float | None = None
    open_price: float | None = None
    previous_close: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    status: QuoteStatus = "unavailable"
    source: str | None = None
    message: str | None = None
    fetched_at: UTCDateTime
    has_hot_alert: bool = False


class QuoteDetailView(QuoteSummaryView):
    is_abnormal: bool = False
    abnormal_reason: str | None = None


class PriceSnapshotView(QuoteDetailView):
    pass


class MarketRefreshResultView(BaseModel):
    quotes_count: int
    symbols: list[str]
    triggered_at: UTCDateTime


class CandlePointView(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


class ValuePointView(BaseModel):
    time: str
    value: float


class MacdPointView(BaseModel):
    time: str
    dif: float
    dea: float
    histogram: float


class KdjPointView(BaseModel):
    time: str
    k: float
    d: float
    j: float


class BollingerPointView(BaseModel):
    time: str
    upper: float
    middle: float
    lower: float


class NewsEventItemView(BaseModel):
    id: int
    title: str
    sentiment: str
    summary: str = ""


class NewsEventGroupView(BaseModel):
    time: str
    items: list[NewsEventItemView]


class IndicatorSeriesView(BaseModel):
    ma5: list[ValuePointView] = Field(default_factory=list)
    ma10: list[ValuePointView] = Field(default_factory=list)
    ma20: list[ValuePointView] = Field(default_factory=list)
    ma60: list[ValuePointView] = Field(default_factory=list)
    macd: list[MacdPointView] = Field(default_factory=list)
    kdj: list[KdjPointView] = Field(default_factory=list)
    bollinger: list[BollingerPointView] = Field(default_factory=list)


class MarketKlineView(BaseModel):
    symbol: str
    interval: str
    range: str
    stale: bool = False
    candles: list[CandlePointView]
    indicators: IndicatorSeriesView
    news_events: list[NewsEventGroupView] = Field(default_factory=list)


class SparklineSeriesView(BaseModel):
    prices: list[float] = Field(default_factory=list)


class MarketSparklineRequest(BaseModel):
    symbols: list[str] = Field(min_length=1)
