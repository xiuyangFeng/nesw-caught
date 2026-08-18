"""量化交易台决策契约：sleeve、期限、状态、point-in-time 记录与版本快照。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Sleeve(StrEnum):
    EVENT_CATALYST = "event_catalyst"
    TREND_FLOW = "trend_flow"
    FUNDAMENTAL_REVALUE = "fundamental_revalue"


class Horizon(StrEnum):
    D1 = "1d"
    D5 = "5d"
    D10 = "10d"
    D20 = "20d"
    D60 = "60d"
    D120 = "120d"


class CandidateState(StrEnum):
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    WATCH = "watch"
    QUALIFIED = "qualified"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class Board(StrEnum):
    MAIN = "main"
    CHINEXT = "chinext"
    STAR = "star"
    BSE = "bse"


class RunStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class PipelineScenario(StrEnum):
    ABSTAIN = "abstain"
    MIXED = "mixed"
    REAL = "real"


@dataclass(frozen=True)
class PitRecord:
    event_at: datetime | None
    source_published_at: datetime | None
    observed_at: datetime
    available_at: datetime


@dataclass(frozen=True)
class FinancialFact:
    symbol: str
    period_end: date
    metric_key: str
    value: float
    available_at: datetime
    revision_no: int
    document_id: str


@dataclass(frozen=True)
class Bar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


@dataclass(frozen=True)
class CorporateAction:
    symbol: str
    action_type: str
    ex_date: date
    available_at: datetime
    cash_ratio: float = 0.0
    share_ratio: float = 0.0


@dataclass(frozen=True)
class SecurityMasterRow:
    symbol: str
    name: str
    exchange: str
    board: Board
    list_date: date
    delist_date: date | None
    status: str
    industry_code: str
    effective_from: date
    effective_to: date | None
    median_amount_20d: float | None = None


@dataclass(frozen=True)
class RunVersions:
    dataset_version: str
    factor_version: str
    rule_version: str
    code_commit: str
    config_snapshot: dict[str, Any]
    source_cutoff: datetime


@dataclass(frozen=True)
class FillDecision:
    filled: bool
    fill_price: float | None
    reason: str


@dataclass
class Candidate:
    symbol: str
    sleeve: Sleeve
    horizon: Horizon
    state: CandidateState
    reason_code: str
    deterministic_score: float
    rank: int | None = None
    invalidation_condition: str | None = None
    valid_until: date | None = None
    factor_breakdown: dict[str, float] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    display_name: str = ""
    thesis_md: str | None = None


@dataclass(frozen=True)
class StageLog:
    stage: str
    status: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    versions: RunVersions
    items: list[Candidate]
    qualified: list[Candidate]
    empty_reason: str | None
    empty_reason_detail: str | None
    result_hash: str
    stages: list[StageLog]
    status: RunStatus = RunStatus.OK
