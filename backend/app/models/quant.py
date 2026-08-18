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


class RadarEvent(Base):
    __tablename__ = "radar_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    news_id: Mapped[int | None] = mapped_column(Integer(), default=None, index=True)
    event_type: Mapped[str] = mapped_column(String(32), default="general")
    evidence_grade: Mapped[str] = mapped_column(String(8), default="C")
    state: Mapped[str] = mapped_column(String(16), index=True)
    reason_code: Mapped[str] = mapped_column(String(64))
    novelty: Mapped[float] = mapped_column(Float(), default=0)
    materiality: Mapped[float] = mapped_column(Float(), default=0)
    score: Mapped[float] = mapped_column(Float(), default=0)
    title: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ResearchSnapshot(Base):
    __tablename__ = "research_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[str] = mapped_column(Text(), default="{}")
    evidence_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class LlmRoleBinding(Base):
    __tablename__ = "llm_role_binding"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(32), unique=True)
    tier: Mapped[str] = mapped_column(String(16), default="standard")
    config_id: Mapped[int | None] = mapped_column(Integer(), default=None)


class AiCallAudit(Base):
    __tablename__ = "ai_call_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="v0")
    cache_hit: Mapped[int] = mapped_column(Integer(), default=0)
    latency_ms: Mapped[float] = mapped_column(Float(), default=0)
    token_in: Mapped[int] = mapped_column(Integer(), default=0)
    token_out: Mapped[int] = mapped_column(Integer(), default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    pool: Mapped[str] = mapped_column(String(32), default="quant_extract")
    detail: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class PortfolioProposal(TimestampMixin, Base):
    __tablename__ = "portfolio_proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(Integer(), default=None, index=True)
    cash_weight: Mapped[float] = mapped_column(Float(), default=1.0)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    payload: Mapped[str] = mapped_column(Text(), default="{}")


class PortfolioProposalItem(Base):
    __tablename__ = "portfolio_proposal_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_proposal.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    sleeve: Mapped[str] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float())
    reject_reason: Mapped[str | None] = mapped_column(String(64), default=None)


class QuantStrategy(TimestampMixin, Base):
    __tablename__ = "quant_strategy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    dsl: Mapped[str] = mapped_column(Text(), default="{}")
    is_active: Mapped[int] = mapped_column(Integer(), default=0)
    exploratory: Mapped[int] = mapped_column(Integer(), default=1)


class QuantBacktestRun(TimestampMixin, Base):
    __tablename__ = "quant_backtest_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    exploratory: Mapped[int] = mapped_column(Integer(), default=1)
    metrics: Mapped[str] = mapped_column(Text(), default="{}")
    note: Mapped[str] = mapped_column(Text(), default="")


class PaperAccount(TimestampMixin, Base):
    __tablename__ = "paper_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="default")
    cash: Mapped[float] = mapped_column(Float(), default=1_000_000)
    initial_cash: Mapped[float] = mapped_column(Float(), default=1_000_000)


class PaperOrder(TimestampMixin, Base):
    __tablename__ = "paper_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer(), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float())
    status: Mapped[str] = mapped_column(String(16), default="accepted")
    reject_reason: Mapped[str | None] = mapped_column(String(64), default=None)
    source: Mapped[str] = mapped_column(String(32), default="manual")


class PaperTrade(TimestampMixin, Base):
    __tablename__ = "paper_trade"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer(), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(Float())
    price: Mapped[float] = mapped_column(Float())


class DecisionLog(TimestampMixin, Base):
    __tablename__ = "decision_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(32), default=None)
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text(), default="")
    payload: Mapped[str] = mapped_column(Text(), default="{}")


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
