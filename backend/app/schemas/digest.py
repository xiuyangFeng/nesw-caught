from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class DigestSectionView(BaseModel):
    """简报中的单个 section（如隔夜重点/自选股相关/情绪方向/风险提示）。"""

    title: str
    body: str


class DigestView(BaseModel):
    """一份完整的每日盘前/盘后 AI 简报。"""

    title: str
    market_scope: str
    generated_at: UTCDateTime
    generated_by: str  # "llm" | "rule"
    model_name: str | None = None
    sections: list[DigestSectionView]


class DigestLatestView(BaseModel):
    """GET /digest/latest 的响应：无最新简报时 available=False。"""

    available: bool
    digest: DigestView | None = None
