from typing import Literal

from pydantic import BaseModel

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


class QuoteDetailView(QuoteSummaryView):
    is_abnormal: bool = False
    abnormal_reason: str | None = None


class PriceSnapshotView(QuoteDetailView):
    pass
