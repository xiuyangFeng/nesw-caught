from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quant import QuantRunStageLog, RecommendationItem, RecommendationRun


class QuantRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_in_progress(self) -> RecommendationRun | None:
        stmt = (
            select(RecommendationRun)
            .where(RecommendationRun.status == "running")
            .order_by(RecommendationRun.id.desc())
        )
        return self.session.scalars(stmt).first()

    def get_latest(self) -> RecommendationRun | None:
        stmt = select(RecommendationRun).order_by(RecommendationRun.id.desc())
        return self.session.scalars(stmt).first()

    def list_items(self, run_id: int) -> list[RecommendationItem]:
        stmt = (
            select(RecommendationItem)
            .where(RecommendationItem.run_id == run_id)
            .order_by(RecommendationItem.sleeve, RecommendationItem.rank, RecommendationItem.id)
        )
        return list(self.session.scalars(stmt))

    def list_stages(self, run_id: int) -> list[QuantRunStageLog]:
        stmt = (
            select(QuantRunStageLog)
            .where(QuantRunStageLog.run_id == run_id)
            .order_by(QuantRunStageLog.id)
        )
        return list(self.session.scalars(stmt))

    def create_run(
        self,
        *,
        run_date: date,
        source_cutoff: datetime,
        trigger: str,
        status: str,
        scenario: str,
        dataset_version: str,
        factor_version: str,
        rule_version: str,
        code_commit: str,
        config_snapshot: dict,
        result_hash: str,
        empty_reason: str | None,
        empty_reason_detail: str | None,
        started_at: datetime,
        finished_at: datetime | None,
    ) -> RecommendationRun:
        row = RecommendationRun(
            run_date=run_date,
            source_cutoff=source_cutoff,
            trigger=trigger,
            status=status,
            scenario=scenario,
            dataset_version=dataset_version,
            factor_version=factor_version,
            rule_version=rule_version,
            code_commit=code_commit,
            config_snapshot=json.dumps(config_snapshot, sort_keys=True, ensure_ascii=False),
            result_hash=result_hash,
            empty_reason=empty_reason,
            empty_reason_detail=empty_reason_detail,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_item(
        self,
        *,
        run_id: int,
        symbol: str,
        display_name: str,
        sleeve: str,
        horizon: str,
        state: str,
        rank: int | None,
        deterministic_score: float,
        reason_code: str,
        factor_breakdown: dict,
        thesis_md: str | None,
        invalidation_condition: str | None,
        valid_until: date | None,
        evidence_ids: list[str],
    ) -> RecommendationItem:
        row = RecommendationItem(
            run_id=run_id,
            symbol=symbol,
            display_name=display_name,
            sleeve=sleeve,
            horizon=horizon,
            state=state,
            rank=rank,
            deterministic_score=deterministic_score,
            reason_code=reason_code,
            factor_breakdown=json.dumps(factor_breakdown, sort_keys=True, ensure_ascii=False),
            thesis_md=thesis_md,
            invalidation_condition=invalidation_condition,
            valid_until=valid_until,
            evidence_ids=json.dumps(evidence_ids, ensure_ascii=False),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_stage(
        self,
        *,
        run_id: int,
        stage: str,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        detail: dict,
    ) -> QuantRunStageLog:
        row = QuantRunStageLog(
            run_id=run_id,
            stage=stage,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            detail=json.dumps(detail, sort_keys=True, ensure_ascii=False),
        )
        self.session.add(row)
        self.session.flush()
        return row
