"""Phase 0 Quant API：无 run 空态、弃权、三 sleeve、幂等重跑。"""

from datetime import date

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

    backtest = client.post("/api/quant/backtests", json={"name": "inflow", "dsl": dsl})
    assert backtest.status_code == 200
    assert backtest.json()["qualified"] is False
    assert backtest.json()["exploratory"] is True

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
