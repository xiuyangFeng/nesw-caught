from typing import Literal

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


# ---------------------------------------------------------------------------
# 市场总览（Market Overview）：/api/market/overview 与指数配置 CRUD
# 契约见 docs/superpowers/specs/2026-08-02-market-overview-design.md 九节。
# ---------------------------------------------------------------------------


class OverviewIndexQuoteView(BaseModel):
    symbol: str
    display_name: str
    kind: str = "index"
    price: float | None = None
    change_percent: float | None = None
    previous_close: float | None = None
    status: str = "unavailable"
    fetched_at: UTCDateTime | None = None


class QuantSentimentInputsView(BaseModel):
    avg_change_percent: float | None = None
    vix: float | None = None
    adv_ratio: float | None = None


class QuantSentimentView(BaseModel):
    score: float | None = None
    label: str = "unknown"
    inputs: QuantSentimentInputsView


class BoardItemView(BaseModel):
    code: str
    name: str | None = None
    price: float | None = None
    change_percent: float | None = None
    advance_count: int | None = None
    decline_count: int | None = None
    flat_count: int | None = None
    net_inflow: float | None = None
    fetched_at: UTCDateTime | None = None


class BoardSectionView(BaseModel):
    status: str  # "ok" / "fetch_failed" / "none"
    stale: bool = False
    source: str  # "eastmoney" / "preset_etf" / "none"
    items: list[BoardItemView] = Field(default_factory=list)
    message: str | None = None


class NewsSignalItemView(BaseModel):
    news_id: int
    title: str
    summary: str | None = None
    signal_confidence: float | None = None
    source_name: str
    published_at: UTCDateTime | None = None
    canonical_url: str


class NewsSentimentView(BaseModel):
    status: str  # "ok" / "insufficient_data"
    score: float | None = None
    sample_count: int = 0
    top_signals: list[NewsSignalItemView] = Field(default_factory=list)


class MarketOverviewMarketView(BaseModel):
    market: str
    display_name: str
    is_open: bool
    indices: list[OverviewIndexQuoteView] = Field(default_factory=list)
    quant_sentiment: QuantSentimentView | None = None
    boards: BoardSectionView
    news_sentiment: NewsSentimentView | None = None


class MarketOverviewView(BaseModel):
    generated_at: UTCDateTime
    markets: list[MarketOverviewMarketView]


class MarketIndexConfigView(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    symbol: str
    market: str
    display_name: str
    kind: str
    sort_order: int
    enabled: bool
    created_at: UTCDateTime | None = None
    updated_at: UTCDateTime | None = None


class MarketIndexConfigCreateRequest(BaseModel):
    symbol: str
    market: str
    display_name: str
    kind: str = "index"
    sort_order: int = 0
    enabled: bool = True


class MarketIndexConfigUpdateRequest(BaseModel):
    # symbol 与 market 不允许改（改了就当删除+新增，语义更清晰）：
    # 请求模型刻意不含这两个字段，extra="forbid" 让显式传入直接 422。
    model_config = {"extra": "forbid"}

    display_name: str | None = None
    kind: str | None = None
    sort_order: int | None = None
    enabled: bool | None = None
