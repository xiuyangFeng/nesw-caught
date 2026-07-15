from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class XRefreshSummary:
    started_at: datetime
    finished_at: datetime
    fetched_count: int
    inserted_count: int
    error: str | None
    latency_ms: float
    skipped: bool = False
    skip_reason: str | None = None
    next_refresh_at: datetime | None = None


@dataclass(frozen=True)
class XAccountsImportSummary:
    created_count: int
    updated_count: int
    skipped_count: int


@dataclass(frozen=True)
class XAccountsExportSummary:
    exported_count: int
