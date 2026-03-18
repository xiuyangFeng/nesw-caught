from pydantic import BaseModel, Field


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    market: str
    display_name: str = Field(min_length=1, max_length=120)
    alert_threshold: float | None = None
    alert_mode: str = "fixed"


class WatchlistItemView(BaseModel):
    id: int
    symbol: str
    market: str
    display_name: str
    is_active: bool
    alert_threshold: float | None = None
    alert_mode: str


class WatchlistCandidateView(BaseModel):
    symbol: str
    market: str
    display_name: str
    aliases: list[str] = []
