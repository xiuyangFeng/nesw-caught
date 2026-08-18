from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class RecommendationRun(TimestampMixin, Base):
    __tablename__ = "recommendation_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_date: Mapped[date] = mapped_column(Date(), index=True)
    source_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(16), index=True)
    scenario: Mapped[str] = mapped_column(String(32), default="abstain")
    dataset_version: Mapped[str] = mapped_column(String(64))
    factor_version: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[str] = mapped_column(String(64))
    code_commit: Mapped[str] = mapped_column(String(64))
    config_snapshot: Mapped[str] = mapped_column(Text())
    result_hash: Mapped[str] = mapped_column(String(64), index=True)
    empty_reason: Mapped[str | None] = mapped_column(String(64), default=None)
    empty_reason_detail: Mapped[str | None] = mapped_column(Text(), default=None)
    llm_config_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class RecommendationItem(Base):
    __tablename__ = "recommendation_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation_run.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    sleeve: Mapped[str] = mapped_column(String(32), index=True)
    horizon: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), index=True)
    rank: Mapped[int | None] = mapped_column(Integer(), default=None)
    deterministic_score: Mapped[float] = mapped_column(Float())
    reason_code: Mapped[str] = mapped_column(String(64))
    factor_breakdown: Mapped[str] = mapped_column(Text(), default="{}")
    thesis_md: Mapped[str | None] = mapped_column(Text(), default=None)
    anti_thesis_md: Mapped[str | None] = mapped_column(Text(), default=None)
    invalidation_condition: Mapped[str | None] = mapped_column(Text(), default=None)
    valid_until: Mapped[date | None] = mapped_column(Date(), default=None)
    evidence_ids: Mapped[str] = mapped_column(Text(), default="[]")


class QuantRunStageLog(Base):
    __tablename__ = "quant_run_stage_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation_run.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    detail: Mapped[str] = mapped_column(Text(), default="{}")
