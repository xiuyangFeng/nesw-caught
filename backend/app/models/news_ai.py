"""AI 漏斗（聚焦改造 P3）的落库结构。

- ``NewsAiScreen``：L1 粗筛，每条新闻一行（标题+摘要批量判断重要度、是否海外、是否精读、译文标题）。
- ``NewsAiAnalysis``：L2 精读，每条新闻一行（中文摘要、明确看法、是否重大事件）。
- ``NewsImpact``：L2 结构化影响，每条新闻多行（板块/个股、方向、强度、理由）；``source`` 区分 AI 与用户修正。
- ``ImpactCorrection``：用户修正记录，作为后续 L2 判断的示例（"传导规则"）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STATUS_OK = "ok"
STATUS_ERROR = "error"

TARGET_STOCK = "stock"
TARGET_SECTOR = "sector"
DIRECTIONS = ("bullish", "bearish", "neutral")
STRENGTHS = ("strong", "medium", "weak")
SOURCE_AI = "ai"
SOURCE_USER = "user"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class NewsAiScreen(Base):
    __tablename__ = "news_ai_screen"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, index=True)
    importance: Mapped[int] = mapped_column(Integer(), default=0)
    overseas: Mapped[bool] = mapped_column(Boolean(), default=False)
    deep_read: Mapped[bool] = mapped_column(Boolean(), default=False, index=True)
    title_zh: Mapped[str | None] = mapped_column(Text(), default=None)
    reason: Mapped[str | None] = mapped_column(Text(), default=None)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_OK, index=True)
    error: Mapped[str | None] = mapped_column(Text(), default=None)
    attempts: Mapped[int] = mapped_column(Integer(), default=0)
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
    screened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)


class NewsAiAnalysis(Base):
    __tablename__ = "news_ai_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, index=True)
    summary_zh: Mapped[str | None] = mapped_column(Text(), default=None)
    view: Mapped[str | None] = mapped_column(Text(), default=None)
    major: Mapped[bool] = mapped_column(Boolean(), default=False)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_OK, index=True)
    error: Mapped[str | None] = mapped_column(Text(), default=None)
    attempts: Mapped[int] = mapped_column(Integer(), default=0)
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)


class NewsImpact(Base):
    __tablename__ = "news_impact"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_code: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    target_name: Mapped[str] = mapped_column(String(128), index=True)
    direction: Mapped[str] = mapped_column(String(16))
    strength: Mapped[str] = mapped_column(String(16))
    rationale: Mapped[str | None] = mapped_column(Text(), default=None)
    source: Mapped[str] = mapped_column(String(16), default=SOURCE_AI)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)


class ImpactCorrection(Base):
    __tablename__ = "impact_correction"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), index=True)
    news_title: Mapped[str] = mapped_column(Text())
    before_json: Mapped[str] = mapped_column(Text())
    after_json: Mapped[str] = mapped_column(Text())
    note: Mapped[str | None] = mapped_column(Text(), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)
