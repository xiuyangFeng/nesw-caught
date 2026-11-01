from typing import Any

from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class AlertView(BaseModel):
    id: int
    kind: str
    severity: str
    symbol: str | None = None
    title: str
    body: str
    payload: dict[str, Any]
    overnight: bool
    created_at: UTCDateTime
    visible_at: UTCDateTime
    read_at: UTCDateTime | None = None


class AlertUnreadCountView(BaseModel):
    unread: int


class AlertReadAllView(BaseModel):
    updated: int
