"""Quant desk persistence and read models for Phase 0 synthetic runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.models.quant import QuantRunStageLog, RecommendationItem, RecommendationRun
from app.repositories.quant_recommendation_repository import QuantRecommendationRepository
from app.schemas.quant import (
    QuantDataStatusView,
    QuantFundFlowPointView,
    QuantFundFlowView,
    QuantRadarCandidateView,
    QuantRadarView,
    QuantRecommendationItemView,
    QuantRecommendationLatestView,
    QuantRecommendationRunView,
    QuantRunStageView,
)
from app.services.quant.contracts import PipelineResult, RunVersions
from app.services.quant.recommendation.pipeline import run_synthetic_pipeline
from app.services.quant.trading_rules import RULE_VERSION

PHASE0_DATASET_VERSION = "synthetic-v0"
PHASE0_FACTOR_VERSION = "synthetic-v0"
PHASE0_CODE_COMMIT = "phase0-skeleton"
PHASE0_CONFIG = {"max_symbol_weight": 0.08, "min_cash": 0.10, "max_positions": 12}
PHASE0_STATUS_NOTE = "量化数据地基已接入独立行情库；未回填时覆盖率为 0。"


class QuantDeskService:
    def get_latest(self, session: Session) -> QuantRecommendationLatestView:
        repo = QuantRecommendationRepository(session)
        run = repo.get_latest()
        if run is None:
            return QuantRecommendationLatestView(
                available=True,
                run=None,
                items=[],
                empty_reason="no_run_yet",
                empty_reason_detail="尚未运行机会流水线。手动重跑将使用合成夹具，现金为合法结果。",
            )
        items = repo.list_items(run.id)
        stages = repo.list_stages(run.id)
        return QuantRecommendationLatestView(
            available=True,
            run=_run_view(run, stages),
            items=[_item_view(item) for item in items],
            empty_reason=run.empty_reason,
            empty_reason_detail=run.empty_reason_detail,
        )

    def run(
        self,
        session: Session,
        *,
        scenario: str = "abstain",
        trigger: str = "manual",
    ) -> QuantRecommendationLatestView:
        repo = QuantRecommendationRepository(session)
        in_progress = repo.get_in_progress()
        if in_progress is not None:
            return self.get_latest(session)

        now = datetime.now(UTC)
        versions = RunVersions(
            dataset_version=PHASE0_DATASET_VERSION,
            factor_version=PHASE0_FACTOR_VERSION,
            rule_version=RULE_VERSION,
            code_commit=PHASE0_CODE_COMMIT,
            config_snapshot=dict(PHASE0_CONFIG),
            source_cutoff=datetime(2026, 4, 10, 7, 30, tzinfo=UTC),
        )
        result = run_synthetic_pipeline(scenario=scenario, versions=versions)
        self._persist(
            repo,
            result,
            scenario=scenario,
            trigger=trigger,
            started_at=now,
            finished_at=datetime.now(UTC),
        )
        return self.get_latest(session)

    def get_data_status(self, session: Session) -> QuantDataStatusView:
        repo = QuantRecommendationRepository(session)
        latest = repo.get_latest()
        coverage = _market_coverage()
        universe = 6141
        coverage_pct = round(100.0 * coverage["symbol_count"] / universe, 2) if universe else 0.0
        return QuantDataStatusView(
            regime="normal",
            coverage_pct=coverage_pct,
            source_cutoff=latest.source_cutoff if latest is not None else datetime(2026, 4, 10, 7, 30, tzinfo=UTC),
            dataset_version=PHASE0_DATASET_VERSION,
            factor_version=PHASE0_FACTOR_VERSION,
            rule_version=RULE_VERSION,
            pit_ready=True,
            backfill_progress_pct=coverage_pct,
            note=PHASE0_STATUS_NOTE,
            last_run_status=latest.status if latest is not None else None,
            daily_bar_count=coverage["daily_bar_count"],
            symbol_count=coverage["symbol_count"],
            fund_flow_count=coverage["fund_flow_count"],
            last_trade_date=coverage["last_trade_date"],
        )

    def get_fund_flow(self, symbol: str) -> QuantFundFlowView:
        points: list[QuantFundFlowPointView] = []
        with MarketSessionLocal() as market_session:
            rows = list(
                market_session.scalars(
                    select(FundFlowDaily)
                    .where(FundFlowDaily.symbol == symbol.upper())
                    .order_by(FundFlowDaily.trade_date.desc())
                    .limit(60)
                )
            )
        for row in reversed(rows):
            points.append(
                QuantFundFlowPointView(
                    trade_date=row.trade_date,
                    main_net_inflow=row.main_net_inflow,
                    super_large_net=row.super_large_net,
                    large_net=row.large_net,
                    medium_net=row.medium_net,
                    small_net=row.small_net,
                    main_net_pct=row.main_net_pct,
                )
            )
        note = None if points else "尚无个股资金流。运行 make quant-backfill 后可见。"
        return QuantFundFlowView(symbol=symbol.upper(), points=points, note=note)

    def get_radar(self, session: Session) -> QuantRadarView:
        latest = self.get_latest(session)
        candidates = [
            QuantRadarCandidateView(
                symbol=item.symbol,
                display_name=item.display_name,
                sleeve=item.sleeve,
                state=item.state,
                reason_code=item.reason_code,
                thesis_md=item.thesis_md,
            )
            for item in latest.items
        ]
        return QuantRadarView(
            as_of=latest.run.source_cutoff if latest.run is not None else None,
            candidates=candidates,
            note="Phase 0 合成事件雷达，快循环尚未接入新闻主链路。",
        )

    def _persist(
        self,
        repo: QuantRecommendationRepository,
        result: PipelineResult,
        *,
        scenario: str,
        trigger: str,
        started_at: datetime,
        finished_at: datetime,
    ) -> RecommendationRun:
        run = repo.create_run(
            run_date=result.versions.source_cutoff.date(),
            source_cutoff=result.versions.source_cutoff,
            trigger=trigger,
            status=result.status.value,
            scenario=scenario,
            dataset_version=result.versions.dataset_version,
            factor_version=result.versions.factor_version,
            rule_version=result.versions.rule_version,
            code_commit=result.versions.code_commit,
            config_snapshot=result.versions.config_snapshot,
            result_hash=result.result_hash,
            empty_reason=result.empty_reason,
            empty_reason_detail=result.empty_reason_detail,
            started_at=started_at,
            finished_at=finished_at,
        )
        for item in result.items:
            repo.add_item(
                run_id=run.id,
                symbol=item.symbol,
                display_name=item.display_name,
                sleeve=item.sleeve.value,
                horizon=item.horizon.value,
                state=item.state.value,
                rank=item.rank,
                deterministic_score=item.deterministic_score,
                reason_code=item.reason_code,
                factor_breakdown=item.factor_breakdown,
                thesis_md=item.thesis_md,
                invalidation_condition=item.invalidation_condition,
                valid_until=item.valid_until,
                evidence_ids=item.evidence_ids,
            )
        for stage in result.stages:
            repo.add_stage(
                run_id=run.id,
                stage=stage.stage,
                status=stage.status,
                started_at=started_at,
                finished_at=finished_at,
                detail=stage.detail,
            )
        return run


def _run_view(run: RecommendationRun, stages: list[QuantRunStageLog]) -> QuantRecommendationRunView:
    return QuantRecommendationRunView(
        id=run.id,
        run_date=run.run_date,
        source_cutoff=run.source_cutoff,
        trigger=run.trigger,
        status=run.status,
        scenario=run.scenario,
        dataset_version=run.dataset_version,
        factor_version=run.factor_version,
        rule_version=run.rule_version,
        code_commit=run.code_commit,
        result_hash=run.result_hash,
        empty_reason=run.empty_reason,
        empty_reason_detail=run.empty_reason_detail,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stages=[
            QuantRunStageView(
                stage=row.stage,
                status=row.status,
                started_at=row.started_at,
                finished_at=row.finished_at,
                detail=json.loads(row.detail),
            )
            for row in stages
        ],
    )


def _item_view(item: RecommendationItem) -> QuantRecommendationItemView:
    return QuantRecommendationItemView(
        symbol=item.symbol,
        display_name=item.display_name,
        sleeve=item.sleeve,
        horizon=item.horizon,
        state=item.state,
        rank=item.rank,
        deterministic_score=item.deterministic_score,
        score_calibrated=False,
        reason_code=item.reason_code,
        factor_breakdown=json.loads(item.factor_breakdown),
        thesis_md=item.thesis_md,
        invalidation_condition=item.invalidation_condition,
        valid_until=item.valid_until,
        evidence_ids=json.loads(item.evidence_ids),
    )


def _market_coverage() -> dict:
    with MarketSessionLocal() as session:
        daily_bar_count = session.scalar(select(func.count()).select_from(DailyBar)) or 0
        symbol_count = session.scalar(select(func.count(func.distinct(DailyBar.symbol)))) or 0
        fund_flow_count = session.scalar(select(func.count()).select_from(FundFlowDaily)) or 0
        last_trade_date = session.scalar(select(func.max(DailyBar.trade_date)))
    return {
        "daily_bar_count": int(daily_bar_count),
        "symbol_count": int(symbol_count),
        "fund_flow_count": int(fund_flow_count),
        "last_trade_date": last_trade_date,
    }
