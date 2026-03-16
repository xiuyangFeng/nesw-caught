from datetime import datetime

from pydantic import BaseModel


class PriceSnapshotView(BaseModel):
    symbol: str
    market: str
    display_name: str | None = None
    price: float
    change_amount: float | None = None
    change_percent: float | None = None
    volume: int | None = None
    is_abnormal: bool = False
    abnormal_reason: str | None = None
    fetched_at: datetime
