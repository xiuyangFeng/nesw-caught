"""Quant desk persistence and read models for Phase 0 synthetic runs."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.quant import (
    AiCallAudit,
    DecisionLog,
    LlmRoleBinding,
    PaperAccount,
    PaperOrder,
    PaperTrade,
    QuantBacktestRun,
    QuantRunStageLog,
    QuantStrategy,
    RadarEvent,
    RecommendationItem,
    RecommendationRun,
    ResearchSnapshot,
)
from app.repositories.quant_recommendation_repository import QuantRecommendationRepository
from app.schemas.quant import (
    QuantAiAuditRowView,
    QuantAiAuditView,
    QuantAiBudgetView,
    QuantAiRoleBindingView,
    QuantBacktestView,
    QuantCopilotToolsView,
    QuantDataStatusView,
    QuantDecisionLogView,
    QuantFactorView,
    QuantFundFlowPointView,
    QuantFundFlowView,
    QuantPaperAccountView,
    QuantPaperOrderView,
    QuantProposalExecuteItemView,
    QuantProposalExecuteView,
    QuantProposalItemView,
    QuantProposalView,
    QuantRadarCandidateView,
    QuantRadarView,
    QuantRecommendationItemView,
    QuantRecommendationLatestView,
    QuantRecommendationRunView,
    QuantReportCardView,
    QuantResearchModuleView,
    QuantResearchPackView,
    QuantRunStageView,
    QuantStrategyView,
    QuantSymbolEventView,
)
from app.services.quant.ai.guard import DEGRADE_ORDER, wrap_untrusted_evidence
from app.services.quant.contracts import PipelineResult, PipelineScenario, RunVersions
from app.services.quant.radar.ingest import list_recent
from app.services.quant.recommendation.market_pipeline import run_market_pipeline
from app.services.quant.recommendation.pipeline import run_synthetic_pipeline
from app.services.quant.research.pack import build_research_pack, latest_financials
from app.services.quant.trading_rules import RULE_VERSION

PHASE0_DATASET_VERSION = "synthetic-v0"
PHASE0_FACTOR_VERSION = "synthetic-v0"
PHASE0_CODE_COMMIT = "phase0-skeleton"
PHASE0_CONFIG = {"max_symbol_weight": 0.08, "min_cash": 0.10, "max_positions": 12}
PHASE0_STATUS_NOTE = "量化数据地基已接入独立行情库；未回填时覆盖率为 0。"
# 真实回测的最小日线数：低于该值无法构成有统计意义的 walk-forward 区间。
MIN_BACKTEST_BARS = 60


def _load_backtest_inputs(
    symbol: str,
    *,
    start_date=None,
    end_date=None,
) -> tuple[list, dict]:
    """读真实日线与资金流，组装 walk_forward 需要的 (bars, features_by_date)。

    特征只用截至当根 bar 的数据：main_inflow_1d 取当日资金流行，adv 取含当日的
    最近 ≤20 根 bar 的均成交额，无前视。
    """
    from app.services.quant.contracts import Bar

    with MarketSessionLocal() as market_session:
        stmt = select(DailyBar).where(DailyBar.symbol == symbol)
        if start_date is not None:
            stmt = stmt.where(DailyBar.trade_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DailyBar.trade_date <= end_date)
        rows = list(market_session.scalars(stmt.order_by(DailyBar.trade_date.asc())))
        flow_stmt = select(FundFlowDaily).where(FundFlowDaily.symbol == symbol)
        if start_date is not None:
            flow_stmt = flow_stmt.where(FundFlowDaily.trade_date >= start_date)
        if end_date is not None:
            flow_stmt = flow_stmt.where(FundFlowDaily.trade_date <= end_date)
        flow_rows = list(market_session.scalars(flow_stmt))

    bars = [
        Bar(row.symbol, row.trade_date, row.open, row.high, row.low, row.close, row.volume, row.amount)
        for row in rows
    ]
    inflow_by_date = {row.trade_date: row.main_net_inflow for row in flow_rows}
    features_by_date: dict = {}
    for index, bar in enumerate(bars):
        window = bars[max(0, index - 19) : index + 1]
        features: dict[str, float] = {
            "adv": sum(item.amount for item in window) / len(window),
        }
        inflow = inflow_by_date.get(bar.trade_date)
        if inflow is not None:
            features["main_inflow_1d"] = inflow
        features_by_date[bar.trade_date] = features
    return bars, features_by_date


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
        scenario: str = "real",
        trigger: str = "manual",
    ) -> QuantRecommendationLatestView:
        repo = QuantRecommendationRepository(session)
        in_progress = repo.get_in_progress()
        if in_progress is not None:
            return self.get_latest(session)

        now = datetime.now(UTC)
        scenario_key = PipelineScenario(scenario)
        if scenario_key is PipelineScenario.REAL:
            versions = RunVersions(
                dataset_version=_real_dataset_version(),
                factor_version="rule-v1",
                rule_version=RULE_VERSION,
                code_commit=PHASE0_CODE_COMMIT,
                config_snapshot=dict(PHASE0_CONFIG),
                source_cutoff=now,
            )
            result = run_market_pipeline(versions=versions)
        else:
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
        scheduled = session.scalar(
            select(RecommendationRun)
            .where(RecommendationRun.trigger == "scheduled")
            .order_by(RecommendationRun.id.desc())
            .limit(1)
        )
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
            last_scheduled_run_date=scheduled.run_date if scheduled is not None else None,
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
        events = list_recent(session, limit=40)
        candidates = [
            QuantRadarCandidateView(
                symbol=row.symbol,
                display_name=row.symbol,
                sleeve="event_catalyst",
                state=row.state,
                reason_code=row.reason_code,
                thesis_md=row.title,
                evidence_grade=row.evidence_grade,
                event_type=row.event_type,
                news_id=row.news_id,
            )
            for row in events
        ]
        if not candidates:
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
            as_of=datetime.now(UTC),
            candidates=candidates,
            note="快循环雷达读取 news mention；D 级传闻不会单独进入 qualified。",
        )

    def get_research(self, session: Session, symbol: str) -> QuantResearchPackView:
        symbol = symbol.upper()
        news_rows = list(
            session.execute(
                select(NewsItem.id, NewsItem.title, NewsItem.source_name, NewsItem.summary)
                .join(NewsStockMention, NewsStockMention.news_id == NewsItem.id)
                .where(NewsStockMention.symbol == symbol)
                .order_by(NewsItem.effective_at.desc())
                .limit(12)
            )
        )
        news = [
            {"id": row.id, "title": row.title, "source_name": row.source_name, "summary": row.summary}
            for row in news_rows
        ]
        financials = latest_financials(symbol)
        pack = build_research_pack(symbol=symbol, display_name=symbol, news=news, financials=financials)
        return QuantResearchPackView(
            symbol=pack.symbol,
            display_name=pack.display_name,
            modules=[
                QuantResearchModuleView(
                    key=module.key,
                    question=module.question,
                    answer=module.answer,
                    evidence_ids=module.evidence_ids,
                    gap=module.gap,
                )
                for module in pack.modules
            ],
            ask_ai_context=wrap_untrusted_evidence(pack.ask_ai_context),
        )

    def refresh_research(self, session: Session, symbol: str) -> QuantResearchPackView:
        pack = self.get_research(session, symbol)
        session.add(
            ResearchSnapshot(
                symbol=pack.symbol,
                display_name=pack.display_name,
                payload=json.dumps(pack.model_dump(mode="json"), ensure_ascii=False),
                evidence_hash=str(hash(pack.ask_ai_context)),
            )
        )
        session.add(
            AiCallAudit(
                role="ThesisBuilder",
                model="rules",
                prompt_version="research-pack-v0",
                status="degraded",
                pool="quant_research",
                detail=json.dumps({"reason": "llm_optional_rules_fallback"}, ensure_ascii=False),
            )
        )
        session.commit()
        return pack

    def list_symbol_events(self, session: Session, symbol: str) -> list[QuantSymbolEventView]:
        rows = list(
            session.scalars(
                select(RadarEvent).where(RadarEvent.symbol == symbol.upper()).order_by(RadarEvent.created_at.desc())
            )
        )
        return [
            QuantSymbolEventView(
                news_id=row.news_id,
                title=row.title,
                evidence_grade=row.evidence_grade,
                event_type=row.event_type,
                state=row.state,
                reason_code=row.reason_code,
            )
            for row in rows
        ]

    def list_role_bindings(self, session: Session) -> list[QuantAiRoleBindingView]:
        roles = ("EvidenceExtractor", "ThesisBuilder", "PeerComparator", "Skeptic", "Copilot")
        existing = {row.role: row for row in session.scalars(select(LlmRoleBinding))}
        views = []
        for role in roles:
            row = existing.get(role)
            views.append(
                QuantAiRoleBindingView(
                    role=role,
                    tier=row.tier if row is not None else ("fast" if role == "EvidenceExtractor" else "deep"),
                    config_id=row.config_id if row is not None else None,
                )
            )
        return views

    def upsert_role_binding(self, session: Session, role: str, config_id: int | None, tier: str) -> QuantAiRoleBindingView:
        row = session.scalar(select(LlmRoleBinding).where(LlmRoleBinding.role == role))
        if row is None:
            row = LlmRoleBinding(role=role, config_id=config_id, tier=tier)
            session.add(row)
        else:
            row.config_id = config_id
            row.tier = tier
        session.commit()
        return QuantAiRoleBindingView(role=row.role, tier=row.tier, config_id=row.config_id)

    def list_ai_audit(self, session: Session, role: str | None = None) -> QuantAiAuditView:
        stmt = select(AiCallAudit).order_by(AiCallAudit.created_at.desc()).limit(100)
        if role:
            stmt = stmt.where(AiCallAudit.role == role)
        rows = list(session.scalars(stmt))
        return QuantAiAuditView(
            items=[
                QuantAiAuditRowView(
                    id=row.id,
                    role=row.role,
                    model=row.model,
                    prompt_version=row.prompt_version,
                    cache_hit=bool(row.cache_hit),
                    latency_ms=row.latency_ms,
                    token_in=row.token_in,
                    token_out=row.token_out,
                    status=row.status,
                    pool=row.pool,
                    created_at=row.created_at,
                )
                for row in rows
            ],
            note="未调用 LLM 时审计可为空；规则研究包刷新会记一条 degraded ThesisBuilder。",
        )

    def get_ai_budget(self) -> QuantAiBudgetView:
        return QuantAiBudgetView(
            pools={
                "quant_extract": "ok",
                "quant_research": "ok",
                "quant_copilot": "independent",
                "quant_review": "ok",
            },
            degrade_order=list(DEGRADE_ORDER),
        )

    def get_proposal(self, session: Session) -> QuantProposalView:
        latest = self.get_latest(session)
        qualified_symbols = [item.symbol for item in latest.items if item.state == "qualified"]
        vol_by_symbol = _volatility_20d(qualified_symbols)
        qualified = [
            (item.symbol, item.sleeve, vol_by_symbol.get(item.symbol, 1.0))
            for item in latest.items
            if item.state == "qualified"
        ]
        from app.services.quant.allocator import allocate

        positions, cash = allocate(qualified)
        return QuantProposalView(
            cash_weight=cash,
            items=[
                QuantProposalItemView(
                    symbol=item.symbol,
                    sleeve=item.sleeve,
                    weight=item.weight,
                    reject_reason=item.reject_reason,
                )
                for item in positions
            ],
            note="无合格机会时现金为 100%。LLM 不参与权重。",
        )

    def get_report_card(self, session: Session, window: str = "30d") -> QuantReportCardView:
        """按 run 时间窗真实聚合：7d/30d/90d 窗口切换产生真实计数差异。"""
        days = {"7d": 7, "30d": 30, "90d": 90}.get(window, 30)
        cutoff = _as_naive_utc(datetime.now(UTC) - timedelta(days=days))
        repo = QuantRecommendationRepository(session)
        runs = [
            run
            for run in repo.list_recent(limit=200)
            if (run.finished_at or run.started_at) is not None
            and _as_naive_utc(run.finished_at or run.started_at) >= cutoff
        ]
        sleeves: dict[str, dict] = {
            "event_catalyst": {"qualified": 0, "watch": 0},
            "trend_flow": {"qualified": 0, "watch": 0},
            "fundamental_revalue": {"qualified": 0, "watch": 0},
        }
        sample_size = 0
        for run in runs:
            for item in repo.list_items(run.id):
                sample_size += 1
                bucket = sleeves.setdefault(item.sleeve, {"qualified": 0, "watch": 0})
                if item.state == "qualified":
                    bucket["qualified"] += 1
                elif item.state == "watch":
                    bucket["watch"] += 1
        return QuantReportCardView(
            window=window,
            sleeves=sleeves,
            sample_size=sample_size,
            note="按窗口内全部 run 聚合漏斗计数；财务未覆盖前不宣称超额收益。",
        )

    def list_runs(self, session: Session) -> list[QuantRecommendationRunView]:
        repo = QuantRecommendationRepository(session)
        return [_run_view(run, repo.list_stages(run.id)) for run in repo.list_recent()]

    def upsert_strategy(self, session: Session, name: str, dsl: dict, is_active: bool) -> QuantStrategyView:
        from app.services.quant.dsl import validate_dsl

        errors = validate_dsl(dsl)
        row = QuantStrategy(
            name=name,
            dsl=json.dumps(dsl, ensure_ascii=False),
            is_active=1 if is_active and not errors else 0,
            exploratory=1,
        )
        session.add(row)
        session.commit()
        return QuantStrategyView(id=row.id, name=row.name, dsl=dsl, is_active=bool(row.is_active), exploratory=True, errors=errors)

    def list_strategies(self, session: Session) -> list[QuantStrategyView]:
        rows = list(session.scalars(select(QuantStrategy).order_by(QuantStrategy.id.desc())))
        return [
            QuantStrategyView(
                id=row.id,
                name=row.name,
                dsl=json.loads(row.dsl),
                is_active=bool(row.is_active),
                exploratory=bool(row.exploratory),
            )
            for row in rows
        ]

    def update_strategy(
        self,
        session: Session,
        strategy_id: int,
        *,
        name: str | None = None,
        dsl: dict | None = None,
        is_active: bool | None = None,
    ) -> QuantStrategyView:
        from app.services.quant.dsl import validate_dsl

        row = session.get(QuantStrategy, strategy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        if dsl is not None:
            errors = validate_dsl(dsl)
            if errors:
                raise HTTPException(status_code=422, detail=f"DSL 校验失败：{', '.join(errors)}")
            row.dsl = json.dumps(dsl, ensure_ascii=False)
        if name is not None:
            row.name = name
        if is_active is not None:
            row.is_active = 1 if is_active else 0
        # exploratory 恒为 1：探索性策略不允许提升为正式（晋级治理后续再做）
        session.commit()
        return QuantStrategyView(
            id=row.id,
            name=row.name,
            dsl=json.loads(row.dsl),
            is_active=bool(row.is_active),
            exploratory=bool(row.exploratory),
        )

    def delete_strategy(self, session: Session, strategy_id: int) -> None:
        row = session.get(QuantStrategy, strategy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="策略不存在")
        session.delete(row)
        session.commit()

    def preview_strategy(self, dsl: dict) -> dict:
        from app.services.quant.dsl import evaluate_dsl, validate_dsl

        errors = validate_dsl(dsl)
        return {"errors": errors, "hit": False if errors else evaluate_dsl(dsl, {"main_inflow_1d": 80_000_000, "news_novelty": 1, "gap_unfilled": 0})}

    def run_backtest(
        self,
        session: Session,
        strategy_id: int | None,
        dsl: dict | None,
        *,
        symbol: str,
        start_date=None,
        end_date=None,
    ) -> QuantBacktestView:
        """真实回测：只吃 market_data.db 的日线/资金流，数据不足显式 coverage_error，绝不回落合成数据。"""
        from app.services.quant.backtest_engine import walk_forward
        from app.services.quant.recommendation.market_pipeline import _infer_board

        symbol = symbol.upper()
        payload = dsl or {"sleeve": "trend_flow", "horizon": "20d", "logic": "and", "conditions": [{"factor": "main_inflow_1d", "op": ">", "value": 1}]}

        bars, features_by_date = _load_backtest_inputs(symbol, start_date=start_date, end_date=end_date)
        coverage_error: str | None = None
        metrics: dict = {}
        if len(bars) < MIN_BACKTEST_BARS:
            coverage_error = (
                f"{symbol} 在选定区间内仅有 {len(bars)} 根日线（需 ≥{MIN_BACKTEST_BARS}），"
                "请先执行 `make quant-backfill` 回填或放宽日期区间。"
            )
            status = "insufficient_data"
        else:
            metrics = walk_forward(
                dsl=payload,
                bars=bars,
                board=_infer_board(symbol),
                features_by_date=features_by_date,
            )
            status = "completed"

        row = QuantBacktestRun(
            strategy_id=strategy_id,
            status=status,
            exploratory=1,
            metrics=json.dumps(metrics),
            note="探索性回测：真实日线驱动；退市股未补齐，不得显示 qualified。",
        )
        session.add(row)
        session.commit()
        return QuantBacktestView(
            id=row.id,
            status=row.status,
            exploratory=True,
            qualified=False,
            symbol=symbol,
            bars_used=len(bars),
            equity_curve=list(metrics.get("equity_curve", [])),
            trades=list(metrics.get("trade_rows", [])),
            coverage_error=coverage_error,
            metrics=metrics,
            note=row.note,
        )

    def get_or_create_paper_account(self, session: Session) -> QuantPaperAccountView:
        row = session.scalar(select(PaperAccount).order_by(PaperAccount.id.asc()))
        if row is None:
            row = PaperAccount(name="default", cash=1_000_000, initial_cash=1_000_000)
            session.add(row)
            session.commit()
        return QuantPaperAccountView(id=row.id, cash=row.cash, initial_cash=row.initial_cash, note="确认后才撮合，不能用生成前价格成交。")

    def place_paper_order(self, session: Session, symbol: str, side: str, quantity: float, confirmed: bool) -> QuantPaperOrderView:
        """按真实行情撮合：实时快照价优先，最新日线收盘价兜底；无行情拒单。"""
        symbol = symbol.upper()
        account = session.scalar(select(PaperAccount).order_by(PaperAccount.id.asc()))
        if account is None:
            account = PaperAccount()
            session.add(account)
            session.flush()

        if not confirmed:
            order = PaperOrder(
                account_id=account.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                status="pending_confirm",
                reject_reason=None,
                source="manual",
            )
            session.add(order)
            session.add(
                DecisionLog(
                    symbol=symbol,
                    action=f"paper_{side}",
                    reason="needs_user_confirm",
                    payload=json.dumps({"confirmed": False}),
                )
            )
            session.commit()
            return QuantPaperOrderView(
                id=order.id,
                status="pending_confirm",
                filled=False,
                reason="needs_user_confirm",
                price=None,
            )

        price_info = self._resolve_fill_price(symbol, side, main_session=session)
        if price_info["reject_reason"] is not None:
            order = PaperOrder(
                account_id=account.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                status="rejected",
                reject_reason=price_info["reject_reason"],
                source="manual",
            )
            session.add(order)
            session.add(
                DecisionLog(
                    symbol=symbol,
                    action=f"paper_{side}",
                    reason=price_info["reject_reason"],
                    payload=json.dumps({"quantity": quantity}),
                )
            )
            session.commit()
            return QuantPaperOrderView(
                id=order.id,
                status="rejected",
                filled=False,
                reason=price_info["reject_reason"],
                price=None,
            )

        price = price_info["price"]
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            status="filled",
            reject_reason=None,
            source="manual",
        )
        session.add(order)
        session.flush()
        session.add(PaperTrade(order_id=order.id, symbol=symbol, quantity=quantity, price=price))
        if side == "buy":
            account.cash -= price * quantity
        else:
            account.cash += price * quantity
        session.add(
            DecisionLog(
                symbol=symbol,
                action=f"paper_{side}",
                reason="filled_at_market",
                payload=json.dumps({"price": price, "quantity": quantity}),
            )
        )
        session.commit()
        return QuantPaperOrderView(
            id=order.id,
            status="filled",
            filled=True,
            reason="filled_at_market",
            price=price,
        )

    def execute_proposal(self, session: Session) -> QuantProposalExecuteView:
        """把最新组合提案按 100 股整数倍换算并逐条下模拟买单；同 run 已执行则拒绝。"""
        latest = self.get_latest(session)
        qualified = [item for item in latest.items if item.state == "qualified"]
        if not qualified:
            raise HTTPException(status_code=404, detail="当前无合格机会，无提案可执行")
        result_hash = latest.run.result_hash if latest.run is not None else None
        existing = session.scalar(
            select(DecisionLog)
            .where(DecisionLog.action == "proposal_execute")
            .order_by(DecisionLog.id.desc())
        )
        if existing is not None:
            payload = json.loads(existing.payload or "{}")
            if payload.get("result_hash") == result_hash:
                raise HTTPException(status_code=409, detail="该提案已执行过")

        proposal = self.get_proposal(session)
        account = session.scalar(select(PaperAccount).order_by(PaperAccount.id.asc()))
        if account is None:
            account = PaperAccount()
            session.add(account)
            session.flush()

        orders: list[QuantProposalExecuteItemView] = []
        for item in proposal.items:
            price_info = self._resolve_fill_price(item.symbol, "buy", main_session=session)
            if price_info["reject_reason"] is not None:
                orders.append(
                    QuantProposalExecuteItemView(
                        symbol=item.symbol,
                        sleeve=item.sleeve,
                        weight=item.weight,
                        filled=False,
                        reject_reason=price_info["reject_reason"],
                    )
                )
                continue
            price = price_info["price"]
            if not price or price <= 0:
                orders.append(
                    QuantProposalExecuteItemView(
                        symbol=item.symbol,
                        sleeve=item.sleeve,
                        weight=item.weight,
                        filled=False,
                        reject_reason="no_market_data",
                    )
                )
                continue
            shares = int(account.cash * item.weight / price // 100) * 100
            if shares < 100:
                orders.append(
                    QuantProposalExecuteItemView(
                        symbol=item.symbol,
                        sleeve=item.sleeve,
                        weight=item.weight,
                        filled=False,
                        reject_reason="below_min_lot",
                    )
                )
                continue
            order = PaperOrder(
                account_id=account.id,
                symbol=item.symbol,
                side="buy",
                quantity=shares,
                status="filled",
                reject_reason=None,
                source="proposal_execute",
            )
            session.add(order)
            session.flush()
            session.add(PaperTrade(order_id=order.id, symbol=item.symbol, quantity=shares, price=price))
            account.cash -= price * shares
            orders.append(
                QuantProposalExecuteItemView(
                    symbol=item.symbol,
                    sleeve=item.sleeve,
                    weight=item.weight,
                    shares=shares,
                    filled=True,
                    fill_price=price,
                )
            )

        session.add(
            DecisionLog(
                symbol=None,
                action="proposal_execute",
                reason="按组合提案下单",
                payload=json.dumps(
                    {
                        "result_hash": result_hash,
                        "symbols": [order.symbol for order in orders if order.filled],
                        "filled": sum(1 for order in orders if order.filled),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        return QuantProposalExecuteView(cash_weight=proposal.cash_weight, orders=orders)

    def _resolve_fill_price(self, symbol: str, side: str, *, main_session: Session) -> dict:
        """解析真实撮合价：实时快照（主库 price_snapshot）优先，最新日线收盘兜底。

        买入侧若最新日线开盘即涨停且锁定（一字板）则拒单；无任何行情返回 no_market_data。
        注意：快照查询复用调用方 main_session，避免在调用方已有未提交写事务时
        再开第二个主库连接（SQLite 写锁互斥会 busy-timeout 报 database is locked）。
        """
        from app.services.quant.recommendation.market_pipeline import _infer_board
        from app.services.quant.trading_rules import is_limit_up_open

        price: float | None = None
        snapshot = main_session.scalar(
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol == symbol)
            .order_by(PriceSnapshot.fetched_at.desc())
            .limit(1)
        )
        if snapshot is not None and snapshot.price and snapshot.price > 0:
            price = float(snapshot.price)

        with MarketSessionLocal() as market_session:
            bars = list(
                market_session.scalars(
                    select(DailyBar)
                    .where(DailyBar.symbol == symbol)
                    .order_by(DailyBar.trade_date.desc())
                    .limit(2)
                )
            )
        if price is None and bars and bars[0].close:
            price = float(bars[0].close)
            if side == "buy" and len(bars) >= 2:
                board = _infer_board(symbol)
                if is_limit_up_open(bars[0].open, bars[1].close, board):
                    locked = bars[0].high == bars[0].low == bars[0].open or bars[0].volume == 0
                    if locked:
                        return {"price": None, "reject_reason": "limit_up_unfilled"}
        if price is None:
            return {"price": None, "reject_reason": "no_market_data"}
        return {"price": price, "reject_reason": None}

    def list_decisions(self, session: Session) -> QuantDecisionLogView:
        rows = list(session.scalars(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(50)))
        return QuantDecisionLogView(
            items=[{"id": row.id, "symbol": row.symbol, "action": row.action, "reason": row.reason} for row in rows]
        )

    def copilot_tools(self) -> QuantCopilotToolsView:
        from app.services.quant.ai.tools import READONLY_TOOLS

        return QuantCopilotToolsView(tools=list(READONLY_TOOLS))

    def list_factors(self) -> list[QuantFactorView]:
        from app.services.quant.factors import FACTOR_REGISTRY

        return [
            QuantFactorView(key=key, sleeve=meta["sleeve"], horizon=meta["horizon"])
            for key, meta in FACTOR_REGISTRY.items()
        ]

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


def _volatility_20d(symbols: list[str]) -> dict[str, float]:
    """qualified 候选的 20 日日收益标准差，供 allocate() 做反波动率加权；样本不足回落 1.0。"""
    vols: dict[str, float] = {}
    if not symbols:
        return vols
    with MarketSessionLocal() as market_session:
        for symbol in symbols:
            bars = list(
                market_session.scalars(
                    select(DailyBar)
                    .where(DailyBar.symbol == symbol)
                    .order_by(DailyBar.trade_date.desc())
                    .limit(21)
                )
            )
            closes = [bar.close for bar in reversed(bars) if bar.close]
            returns = [
                (closes[i] - closes[i - 1]) / closes[i - 1]
                for i in range(1, len(closes))
                if closes[i - 1]
            ]
            if len(returns) >= 2:
                vols[symbol] = statistics.pstdev(returns) or 1.0
    return vols


def _as_naive_utc(value: datetime) -> datetime:
    """SQLite 的 DateTime(timezone=True) 不保真时区：读回可能是 naive，统一剥离 tzinfo 再比较。"""
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _real_dataset_version() -> str:
    """real scenario 的 dataset_version：eastmoney-daily-{最新交易日}，无数据时落回 unknown
    （此时 run_market_pipeline 会自行判定 DEGRADED，这里只负责给版本号一个可读占位）。"""
    with MarketSessionLocal() as market_session:
        last_trade_date = market_session.scalar(select(func.max(DailyBar.trade_date)))
    return f"eastmoney-daily-{last_trade_date.isoformat() if last_trade_date else 'unknown'}"


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
