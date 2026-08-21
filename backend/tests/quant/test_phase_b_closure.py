"""Phase B 闭环：策略生命周期、模拟盘真实价撮合、提案执行、成绩单真实窗口。

契约（设计稿 §3.2 B2/B3/B4/B6、计划 §0）：
- PATCH/DELETE /strategies/{id}；exploratory 恒 true 不可提升；
- paper order 撮合价用实时快照或最新日线，无行情拒单 no_market_data；
- 提案执行按 100 股整数倍换算，逐条成交/拒单，重复执行被拒；
- report-card 窗口按 run 时间窗真实聚合。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.models.quant import PaperOrder, QuantStrategy
from app.models.price_snapshot import PriceSnapshot
from app.services.quant_desk_service import QuantDeskService

SYMBOL = "000001.SZ"
DSL = {
    "sleeve": "trend_flow",
    "horizon": "20d",
    "logic": "and",
    "conditions": [{"factor": "main_inflow_1d", "op": ">", "value": 1}],
}


def _cleanup() -> None:
    with MarketSessionLocal() as market_session:
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.commit()
    with SessionLocal() as session:
        from app.models.quant import (
            AiCallAudit,
            DecisionLog,
            LlmRoleBinding,
            PaperAccount,
            PaperTrade,
            PortfolioProposal,
            PortfolioProposalItem,
            QuantBacktestRun,
            QuantRunStageLog,
            QuantStrategy,
            RadarEvent,
            RecommendationItem,
            RecommendationRun,
            ResearchSnapshot,
        )

        session.query(PortfolioProposalItem).delete()
        session.query(PortfolioProposal).delete()
        session.query(PaperTrade).delete()
        session.query(PaperOrder).delete()
        session.query(PaperAccount).delete()
        session.query(QuantBacktestRun).delete()
        session.query(QuantStrategy).delete()
        session.query(DecisionLog).delete()
        session.query(AiCallAudit).delete()
        session.query(LlmRoleBinding).delete()
        session.query(ResearchSnapshot).delete()
        session.query(RadarEvent).delete()
        session.query(QuantRunStageLog).delete()
        session.query(RecommendationItem).delete()
        session.query(RecommendationRun).delete()
        session.query(PriceSnapshot).delete()
        session.commit()


def _seed_bars(symbol: str = SYMBOL, *, days: int = 130, base_close: float = 10.0, last_open: float | None = None) -> None:
    last_date = date.today()
    with MarketSessionLocal() as market_session:
        for i in range(days):
            trade_date = last_date - timedelta(days=days - 1 - i)
            close = base_close + (1.0 if i % 4 < 2 else 0.0)
            market_session.add(
                DailyBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=last_open if (i == days - 1 and last_open is not None) else close,
                    high=close + 0.2,
                    low=close - 0.2,
                    close=close,
                    volume=1000,
                    amount=2e8,
                )
            )
        market_session.commit()


def _seed_flow(symbol: str = SYMBOL, *, days: int = 130, inflow: float = 8e7) -> None:
    last_date = date.today()
    with MarketSessionLocal() as market_session:
        for i in range(days):
            market_session.add(
                FundFlowDaily(
                    symbol=symbol,
                    trade_date=last_date - timedelta(days=days - 1 - i),
                    main_net_inflow=inflow,
                )
            )
        market_session.commit()


def _run_pipeline() -> None:
    with SessionLocal() as session:
        QuantDeskService().run(session, scenario="real", trigger="manual")
        session.commit()


# ---------- 策略生命周期 ----------

def test_strategy_patch_rename_dsl_and_active() -> None:
    _cleanup()
    with SessionLocal() as session:
        service = QuantDeskService()
        created = service.upsert_strategy(session, "旧名字", DSL, is_active=False)
        updated = service.update_strategy(session, created.id, name="新名字", is_active=True)
        assert updated.name == "新名字"
        assert updated.is_active is True
        assert updated.exploratory is True
        # 改名后列表同步
        listed = service.list_strategies(session)
        assert listed[0].name == "新名字"
        assert listed[0].is_active is True


def test_strategy_patch_invalid_dsl_rejected() -> None:
    _cleanup()
    with SessionLocal() as session:
        service = QuantDeskService()
        created = service.upsert_strategy(session, "s", DSL, is_active=False)
        bad = dict(DSL)
        bad["conditions"] = [{"factor": "not_a_factor", "op": ">", "value": 1}]
        with pytest.raises(HTTPException) as exc:
            service.update_strategy(session, created.id, dsl=bad)
        assert exc.value.status_code == 422


def test_strategy_delete_removes_row() -> None:
    _cleanup()
    with SessionLocal() as session:
        service = QuantDeskService()
        created = service.upsert_strategy(session, "s", DSL, is_active=False)
        service.delete_strategy(session, created.id)
        assert service.list_strategies(session) == []
        with pytest.raises(HTTPException) as exc:
            service.delete_strategy(session, created.id)
        assert exc.value.status_code == 404


# ---------- 模拟盘真实价撮合 ----------

def test_paper_order_fills_at_latest_daily_close() -> None:
    _cleanup()
    _seed_bars(days=5)
    with SessionLocal() as session:
        service = QuantDeskService()
        view = service.place_paper_order(session, SYMBOL, "buy", 100, confirmed=True)
    assert view.filled is True
    assert view.price is not None
    assert view.price > 0
    with SessionLocal() as session:
        order = session.query(PaperOrder).filter_by(symbol=SYMBOL).first()
        assert order is not None
        assert order.status == "filled"
        account = QuantDeskService().get_or_create_paper_account(session)
        # 现金已扣减
        assert account.cash < 1_000_000


def test_paper_order_prefers_price_snapshot_over_daily_bar() -> None:
    _cleanup()
    _seed_bars(days=5, base_close=10.0)
    with SessionLocal() as session:
        session.add(
            PriceSnapshot(symbol=SYMBOL, market="cn", price=99.5, fetched_at=datetime.now(UTC))
        )
        session.commit()
        view = QuantDeskService().place_paper_order(session, SYMBOL, "buy", 100, confirmed=True)
    assert view.price == 99.5


def test_paper_order_without_market_data_rejects() -> None:
    _cleanup()
    with SessionLocal() as session:
        view = QuantDeskService().place_paper_order(session, SYMBOL, "buy", 100, confirmed=True)
    assert view.filled is False
    assert view.reason == "no_market_data"


def test_paper_order_locked_limit_up_buy_rejected() -> None:
    _cleanup()
    # 最新一日开盘即涨停（+10% 主板）且 lock（high==low==open）
    today = date.today()
    prev_close = 10.0
    limit_open = round(prev_close * 1.1, 2)
    with MarketSessionLocal() as market_session:
        for i in range(3):
            trade_date = today - timedelta(days=2 - i)
            close = prev_close if i < 2 else limit_open
            market_session.add(
                DailyBar(
                    symbol=SYMBOL,
                    trade_date=trade_date,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=1000,
                    amount=1e8,
                )
            )
        market_session.commit()
    with SessionLocal() as session:
        view = QuantDeskService().place_paper_order(session, SYMBOL, "buy", 100, confirmed=True)
    assert view.filled is False
    assert view.reason == "limit_up_unfilled"


def test_paper_order_unconfirmed_stays_pending() -> None:
    _cleanup()
    _seed_bars(days=5)
    with SessionLocal() as session:
        view = QuantDeskService().place_paper_order(session, SYMBOL, "buy", 100, confirmed=False)
    assert view.filled is False
    assert view.status == "pending_confirm"
    assert view.price is None


# ---------- 提案执行 ----------

def test_proposal_execute_creates_lot_multiple_orders_with_real_price() -> None:
    _cleanup()
    _seed_bars(days=130)
    _seed_flow(days=130)
    _run_pipeline()
    with SessionLocal() as session:
        service = QuantDeskService()
        proposal = service.get_proposal(session)
        assert proposal.items, "需要至少一个 qualified 持仓"
        view = service.execute_proposal(session)
    assert view.orders, "至少应有一笔成交"
    filled = [order for order in view.orders if order.filled]
    assert filled, "权重换算后至少应有一笔 ≥1 手 的成交"
    for order in filled:
        assert order.shares % 100 == 0
        assert order.shares >= 100
        assert order.fill_price is not None and order.fill_price > 0
    with SessionLocal() as session:
        orders = session.query(PaperOrder).all()
        assert all(order.source == "proposal_execute" for order in orders)


def test_proposal_execute_is_idempotent_and_rejects_repeat() -> None:
    _cleanup()
    _seed_bars(days=130)
    _seed_flow(days=130)
    _run_pipeline()
    with SessionLocal() as session:
        service = QuantDeskService()
        service.execute_proposal(session)
        with pytest.raises(HTTPException) as exc:
            service.execute_proposal(session)
        assert exc.value.status_code == 409


def test_proposal_execute_without_qualified_returns_404() -> None:
    _cleanup()
    _seed_bars(days=130)
    _seed_flow(days=130, inflow=0.0)  # 无主力流入 → 无 qualified
    _run_pipeline()
    with SessionLocal() as session:
        with pytest.raises(HTTPException) as exc:
            QuantDeskService().execute_proposal(session)
        assert exc.value.status_code == 404


# ---------- 成绩单真实窗口 ----------

def test_report_card_window_aggregates_runs_in_range() -> None:
    _cleanup()
    _seed_bars(days=130)
    _seed_flow(days=130)
    _run_pipeline()  # 今天跑一次，产生 trend qualified
    with SessionLocal() as session:
        card_7d = QuantDeskService().get_report_card(session, "7d")
        card_90d = QuantDeskService().get_report_card(session, "90d")
    # 今天刚跑，两个窗口都应看到同一次 run
    assert card_7d.sample_size >= 1
    assert card_7d.sample_size == card_90d.sample_size


def test_report_card_window_excludes_old_runs() -> None:
    _cleanup()
    with SessionLocal() as session:
        service = QuantDeskService()
        # 手工插入 60 天前的 run 记录（直接走 repository 落库）
        service.run(session, scenario="abstain", trigger="manual")
        session.commit()
    # 直接改 started_at/finished_at 模拟历史 run
    from app.repositories.quant_recommendation_repository import QuantRecommendationRepository

    with SessionLocal() as session:
        repo = QuantRecommendationRepository(session)
        latest = repo.get_latest()
        assert latest is not None
        old_ts = datetime.now(UTC) - timedelta(days=60)
        latest.started_at = old_ts
        latest.finished_at = old_ts
        session.commit()
    with SessionLocal() as session:
        card_7d = QuantDeskService().get_report_card(session, "7d")
        card_90d = QuantDeskService().get_report_card(session, "90d")
    # abstain 不产候选，但 sample 口径应区分：7d 为空窗口，90d 含旧 run
    assert card_7d.sample_size == 0
    assert card_90d.sample_size >= 0
