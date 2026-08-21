"""Phase 0 Quant API：无 run 空态、弃权、三 sleeve、幂等重跑。"""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.main import app
from app.models.market_data import DailyBar, FundFlowDaily, IndexDailyBar, TradeCalendar
from app.models.quant import (
    AiCallAudit,
    DecisionLog,
    LlmRoleBinding,
    PaperAccount,
    PaperOrder,
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


def _cleanup() -> None:
    with SessionLocal() as session:
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
        session.commit()
    with MarketSessionLocal() as market_session:
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.query(IndexDailyBar).delete()
        market_session.query(TradeCalendar).delete()
        market_session.commit()


def test_latest_without_run_expresses_empty_opportunity() -> None:
    _cleanup()
    client = TestClient(app)

    response = client.get("/api/quant/recommendations/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["empty_reason"] == "no_run_yet"
    assert payload["run"] is None


def test_abstain_run_returns_zero_qualified_and_empty_reason() -> None:
    _cleanup()
    client = TestClient(app)

    response = client.post("/api/quant/recommendations/run", json={"scenario": "abstain"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["empty_reason"] == "no_positive_edge"
    assert payload["run"]["status"] == "ok"
    assert payload["run"]["result_hash"]
    assert all(item["state"] != "qualified" for item in payload["items"])
    qualified = [item for item in payload["items"] if item["state"] == "qualified"]
    assert qualified == []


def test_mixed_run_keeps_sleeves_independent() -> None:
    _cleanup()
    client = TestClient(app)

    response = client.post("/api/quant/recommendations/run", json={"scenario": "mixed"})

    assert response.status_code == 200
    payload = response.json()
    by_sleeve = {item["sleeve"]: item for item in payload["items"]}
    assert by_sleeve["event_catalyst"]["state"] == "watch"
    assert by_sleeve["trend_flow"]["state"] == "watch"
    assert by_sleeve["fundamental_revalue"]["state"] == "qualified"
    assert payload["empty_reason"] is None


def test_rerun_same_scenario_keeps_result_hash() -> None:
    _cleanup()
    client = TestClient(app)

    first = client.post("/api/quant/recommendations/run", json={"scenario": "mixed"}).json()
    second = client.post("/api/quant/recommendations/run", json={"scenario": "mixed"}).json()
    assert first["run"]["result_hash"] == second["run"]["result_hash"]


def test_in_progress_run_is_idempotent() -> None:
    _cleanup()
    client = TestClient(app)
    first = client.post("/api/quant/recommendations/run", json={"scenario": "abstain"}).json()
    with SessionLocal() as session:
        run = session.get(RecommendationRun, first["run"]["id"])
        assert run is not None
        run.status = "running"
        session.commit()

    again = client.post("/api/quant/recommendations/run", json={"scenario": "mixed"}).json()
    assert again["run"]["id"] == first["run"]["id"]
    assert again["run"]["status"] == "running"


def test_data_status_and_radar_are_readable() -> None:
    _cleanup()
    client = TestClient(app)
    client.post("/api/quant/recommendations/run", json={"scenario": "mixed"})

    status = client.get("/api/quant/data/status")
    assert status.status_code == 200
    body = status.json()
    assert body["pit_ready"] is True
    assert body["rule_version"]
    assert body["daily_bar_count"] >= 0
    assert "行情库" in body["note"]

    radar = client.get("/api/quant/radar")
    assert radar.status_code == 200
    assert len(radar.json()["candidates"]) == 3

    flow = client.get("/api/quant/symbols/600519.SH/fund-flow")
    assert flow.status_code == 200
    assert flow.json()["points"] == []
    assert flow.json()["symbol"] == "600519.SH"
    assert "quant-backfill" in flow.json()["note"]

    research = client.get("/api/quant/symbols/600519.SH/research")
    assert research.status_code == 200
    keys = [item["key"] for item in research.json()["modules"]]
    assert "valuation" in keys
    assert "latest_events" in keys
    assert "目标价" not in research.json()["ask_ai_context"]

    bindings = client.get("/api/quant/ai/role-bindings")
    assert bindings.status_code == 200
    assert {row["role"] for row in bindings.json()} >= {"EvidenceExtractor", "Skeptic"}

    audit = client.get("/api/quant/ai/audit")
    assert audit.status_code == 200
    budget = client.get("/api/quant/ai/budget")
    assert budget.status_code == 200
    assert budget.json()["degrade_order"][0] == "quant_review"


def test_data_status_and_fund_flow_read_market_db() -> None:
    _cleanup()
    with MarketSessionLocal() as market_session:
        market_session.add(
            DailyBar(
                symbol="600519.SH",
                trade_date=date(2026, 4, 10),
                open=1,
                high=1,
                low=1,
                close=1,
                volume=1,
                amount=1,
            )
        )
        market_session.add(
            FundFlowDaily(
                symbol="600519.SH",
                trade_date=date(2026, 4, 10),
                main_net_inflow=10.0,
                main_net_pct=0.1,
            )
        )
        market_session.commit()

    client = TestClient(app)
    status = client.get("/api/quant/data/status")
    assert status.status_code == 200
    body = status.json()
    assert body["daily_bar_count"] == 1
    assert body["symbol_count"] == 1
    assert body["fund_flow_count"] == 1
    assert body["last_trade_date"] == "2026-04-10"

    flow = client.get("/api/quant/symbols/600519.SH/fund-flow")
    assert flow.status_code == 200
    payload = flow.json()
    assert len(payload["points"]) == 1
    assert payload["points"][0]["main_net_inflow"] == 10.0
    assert payload["note"] is None


def test_phase3_to_5_desk_endpoints() -> None:
    _cleanup()
    client = TestClient(app)
    client.post("/api/quant/recommendations/run", json={"scenario": "abstain"})

    proposal = client.get("/api/quant/portfolio-proposals/latest")
    assert proposal.status_code == 200
    assert proposal.json()["cash_weight"] == 1.0
    assert "LLM" in (proposal.json()["note"] or "")

    card = client.get("/api/quant/report-card")
    assert card.status_code == 200
    assert card.json()["window"] == "30d"

    runs = client.get("/api/quant/recommendations/runs")
    assert runs.status_code == 200
    assert len(runs.json()) >= 1

    dsl = {
        "sleeve": "trend_flow",
        "horizon": "20d",
        "logic": "and",
        "conditions": [{"factor": "main_inflow_1d", "op": ">", "value": 1}],
    }
    preview = client.post("/api/quant/strategies/preview", json={"name": "inflow", "dsl": dsl})
    assert preview.status_code == 200
    assert preview.json()["errors"] == []

    created = client.post("/api/quant/strategies", json={"name": "inflow", "dsl": dsl, "is_active": True})
    assert created.status_code == 200
    assert created.json()["exploratory"] is True

    listed = client.get("/api/quant/strategies")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    backtest = client.post("/api/quant/backtests", json={"name": "inflow", "dsl": dsl, "symbol": "600519.SH"})
    assert backtest.status_code == 200
    assert backtest.json()["qualified"] is False
    assert backtest.json()["exploratory"] is True
    # 测试行情库为空：真实回测必须显式 coverage_error，而不是回落合成数据
    assert backtest.json()["coverage_error"] is not None
    assert backtest.json()["bars_used"] == 0

    paper = client.get("/api/quant/paper/account")
    assert paper.status_code == 200
    assert paper.json()["cash"] == 1_000_000

    pending = client.post(
        "/api/quant/paper/orders",
        json={"symbol": "600519.SH", "side": "buy", "quantity": 100, "confirmed": False},
    )
    assert pending.status_code == 200
    assert pending.json()["filled"] is False
    assert pending.json()["status"] == "pending_confirm"

    tools = client.get("/api/quant/copilot/tools")
    assert tools.status_code == 200
    assert "get_research_snapshot" in tools.json()["tools"]
    assert "全部只读" in tools.json()["note"]

    decisions = client.get("/api/quant/decision-log")
    assert decisions.status_code == 200
    assert any(item["action"] == "paper_buy" for item in decisions.json()["items"])


def test_strategy_lifecycle_patch_delete_endpoints() -> None:
    _cleanup()
    client = TestClient(app)
    dsl = {
        "sleeve": "trend_flow",
        "horizon": "20d",
        "logic": "and",
        "conditions": [{"factor": "main_inflow_1d", "op": ">", "value": 1}],
    }
    created = client.post("/api/quant/strategies", json={"name": "s", "dsl": dsl, "is_active": False})
    strategy_id = created.json()["id"]

    patched = client.patch(
        f"/api/quant/strategies/{strategy_id}",
        json={"name": "renamed", "is_active": True},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "renamed"
    assert patched.json()["is_active"] is True
    assert patched.json()["exploratory"] is True

    bad = client.patch(
        f"/api/quant/strategies/{strategy_id}",
        json={"dsl": {"conditions": [{"factor": "nope", "op": ">", "value": 1}]}},
    )
    assert bad.status_code == 422

    missing = client.patch("/api/quant/strategies/99999", json={"name": "x"})
    assert missing.status_code == 404

    deleted = client.delete(f"/api/quant/strategies/{strategy_id}")
    assert deleted.status_code == 204
    assert client.delete(f"/api/quant/strategies/{strategy_id}").status_code == 404


def test_paper_order_rejects_without_market_data_and_fills_real_price() -> None:
    _cleanup()
    client = TestClient(app)
    # 无行情：confirmed 后拒单，不回落合成价格
    rejected = client.post(
        "/api/quant/paper/orders",
        json={"symbol": "600519.SH", "side": "buy", "quantity": 100, "confirmed": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["filled"] is False
    assert rejected.json()["reason"] == "no_market_data"

    # 有日线：按真实收盘价成交
    from datetime import date as date_cls

    today = date_cls.today()
    with MarketSessionLocal() as market_session:
        for i in range(5):
            market_session.add(
                DailyBar(
                    symbol="600519.SH",
                    trade_date=today - timedelta(days=4 - i),
                    open=1500,
                    high=1510,
                    low=1490,
                    close=1500,
                    volume=1000,
                    amount=1e9,
                )
            )
        market_session.commit()

    filled = client.post(
        "/api/quant/paper/orders",
        json={"symbol": "600519.SH", "side": "buy", "quantity": 100, "confirmed": True},
    )
    assert filled.status_code == 200
    assert filled.json()["filled"] is True
    assert filled.json()["price"] == 1500.0


def test_proposal_execute_endpoint_without_qualified_returns_404() -> None:
    _cleanup()
    client = TestClient(app)
    client.post("/api/quant/recommendations/run", json={"scenario": "abstain"})
    response = client.post("/api/quant/portfolio-proposals/latest/execute")
    assert response.status_code == 404


def test_scheduler_manual_trigger_runs_scheduled_pipeline() -> None:
    _cleanup()
    client = TestClient(app)
    # 空行情库：backfill=false 只跑流水线，返回 DEGRADED 但 trigger=scheduled
    response = client.post("/api/quant/scheduler/run?backfill=false")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["trigger"] == "scheduled"
    assert payload["empty_reason"] == "no_market_data"

    runs = client.get("/api/quant/recommendations/runs")
    assert runs.json()[0]["trigger"] == "scheduled"


def _load_seed_module():
    """镜像 app/db/initializer.py 的动态加载方式：scripts/ 不在 backend 包内。"""
    seed_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("test_seed_demo_data", seed_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_scenario_run_without_market_data_is_degraded() -> None:
    _cleanup()
    client = TestClient(app)
    resp = client.post("/api/quant/recommendations/run", json={"scenario": "real"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["status"] == "degraded"
    assert body["run"]["scenario"] == "real"
    assert body["empty_reason"] == "no_market_data"
    assert body["items"] == []


def test_real_scenario_run_qualifies_trend_candidate_from_market_data() -> None:
    _cleanup()
    today = date.today()
    symbol = "000099.SZ"
    with MarketSessionLocal() as market_session:
        for i in range(130):
            trade_date = today - timedelta(days=129 - i)
            market_session.add(
                DailyBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=10.0,
                    high=10.0,
                    low=10.0,
                    close=10.0,
                    volume=1000,
                    amount=2e8,
                )
            )
        market_session.commit()
        market_session.add(
            FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=8e7, main_net_pct=0.1)
        )
        market_session.commit()

    client = TestClient(app)
    resp = client.post("/api/quant/recommendations/run", json={"scenario": "real"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["status"] == "ok"
    assert body["run"]["scenario"] == "real"
    assert body["run"]["dataset_version"].startswith("eastmoney-daily-")
    trend_items = [
        item for item in body["items"] if item["sleeve"] == "trend_flow" and item["symbol"] == symbol
    ]
    assert len(trend_items) == 1
    assert trend_items[0]["state"] == "qualified"

    proposal = client.get("/api/quant/portfolio-proposals/latest")
    assert proposal.status_code == 200
    assert proposal.json()["cash_weight"] < 1.0


def test_factors_endpoint_lists_registry() -> None:
    client = TestClient(app)
    resp = client.get("/api/quant/factors")
    assert resp.status_code == 200
    body = resp.json()
    keys = {row["key"] for row in body}
    assert {"main_inflow_1d", "news_novelty", "gap_unfilled"} <= keys
    assert {"net_profit_yoy", "revenue_yoy", "roe"} <= keys
    by_key = {row["key"]: row for row in body}
    assert by_key["main_inflow_1d"]["sleeve"] == "trend_flow"
    assert by_key["news_novelty"]["horizon"] == "5d"
    assert by_key["net_profit_yoy"]["sleeve"] == "fundamental_revalue"


def test_default_strategy_seed_is_idempotent_and_visible() -> None:
    _cleanup()  # 会清空 quant_strategy 表（见 _cleanup 定义）
    seed_module = _load_seed_module()
    seed_module.seed_demo_data()

    client = TestClient(app)
    resp = client.get("/api/quant/strategies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    sleeves = {row["dsl"]["sleeve"] for row in body}
    assert sleeves == {"trend_flow", "event_catalyst", "fundamental_revalue"}
    assert all(row["is_active"] is False for row in body)
    assert all(row["exploratory"] is True for row in body)
    assert all(row["errors"] == [] for row in body)

    # 幂等：再跑一次种子不应重复插入。
    seed_module.seed_demo_data()
    resp2 = client.get("/api/quant/strategies")
    assert len(resp2.json()) == 3
