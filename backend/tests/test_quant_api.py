"""Phase 0 Quant API：无 run 空态、弃权、三 sleeve、幂等重跑。"""

from datetime import date

from fastapi.testclient import TestClient

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.main import app
from app.models.market_data import DailyBar, FundFlowDaily, IndexDailyBar, TradeCalendar
from app.models.quant import QuantRunStageLog, RecommendationItem, RecommendationRun


def _cleanup() -> None:
    with SessionLocal() as session:
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
