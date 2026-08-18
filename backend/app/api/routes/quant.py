from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.quant import (
    QuantAiAuditView,
    QuantAiBudgetView,
    QuantAiRoleBindingUpdate,
    QuantAiRoleBindingView,
    QuantBacktestView,
    QuantCopilotToolsView,
    QuantDataStatusView,
    QuantDecisionLogView,
    QuantFactorView,
    QuantFundFlowView,
    QuantPaperAccountView,
    QuantPaperOrderRequest,
    QuantPaperOrderView,
    QuantProposalView,
    QuantRadarView,
    QuantRecommendationLatestView,
    QuantRecommendationRunView,
    QuantReportCardView,
    QuantResearchPackView,
    QuantRunRequest,
    QuantStrategyUpsert,
    QuantStrategyView,
    QuantSymbolEventView,
)
from app.services.quant_desk_service import QuantDeskService

router = APIRouter()


@router.get("/recommendations/latest", response_model=QuantRecommendationLatestView)
def get_latest_recommendations(
    session: Session = Depends(get_db_session),
) -> QuantRecommendationLatestView:
    return QuantDeskService().get_latest(session)


@router.post("/recommendations/run", response_model=QuantRecommendationLatestView)
def run_recommendations(
    payload: QuantRunRequest | None = None,
    session: Session = Depends(get_db_session),
) -> QuantRecommendationLatestView:
    body = payload or QuantRunRequest()
    return QuantDeskService().run(session, scenario=body.scenario, trigger=body.trigger)


@router.get("/data/status", response_model=QuantDataStatusView)
def get_quant_data_status(session: Session = Depends(get_db_session)) -> QuantDataStatusView:
    return QuantDeskService().get_data_status(session)


@router.get("/factors", response_model=list[QuantFactorView])
def get_quant_factors() -> list[QuantFactorView]:
    return QuantDeskService().list_factors()


@router.get("/radar", response_model=QuantRadarView)
def get_quant_radar(session: Session = Depends(get_db_session)) -> QuantRadarView:
    return QuantDeskService().get_radar(session)


@router.get("/symbols/{symbol}/fund-flow", response_model=QuantFundFlowView)
def get_symbol_fund_flow(symbol: str) -> QuantFundFlowView:
    return QuantDeskService().get_fund_flow(symbol)


@router.get("/symbols/{symbol}/research", response_model=QuantResearchPackView)
def get_symbol_research(symbol: str, session: Session = Depends(get_db_session)) -> QuantResearchPackView:
    return QuantDeskService().get_research(session, symbol)


@router.post("/symbols/{symbol}/research/refresh", response_model=QuantResearchPackView)
def refresh_symbol_research(symbol: str, session: Session = Depends(get_db_session)) -> QuantResearchPackView:
    return QuantDeskService().refresh_research(session, symbol)


@router.get("/symbols/{symbol}/events", response_model=list[QuantSymbolEventView])
def get_symbol_events(symbol: str, session: Session = Depends(get_db_session)) -> list[QuantSymbolEventView]:
    return QuantDeskService().list_symbol_events(session, symbol)


@router.get("/ai/role-bindings", response_model=list[QuantAiRoleBindingView])
def get_role_bindings(session: Session = Depends(get_db_session)) -> list[QuantAiRoleBindingView]:
    return QuantDeskService().list_role_bindings(session)


@router.put("/ai/role-bindings", response_model=QuantAiRoleBindingView)
def put_role_binding(
    payload: QuantAiRoleBindingUpdate,
    session: Session = Depends(get_db_session),
) -> QuantAiRoleBindingView:
    return QuantDeskService().upsert_role_binding(session, payload.role, payload.config_id, payload.tier)


@router.get("/ai/audit", response_model=QuantAiAuditView)
def get_ai_audit(role: str | None = None, session: Session = Depends(get_db_session)) -> QuantAiAuditView:
    return QuantDeskService().list_ai_audit(session, role)


@router.get("/ai/budget", response_model=QuantAiBudgetView)
def get_ai_budget() -> QuantAiBudgetView:
    return QuantDeskService().get_ai_budget()


@router.get("/recommendations/runs", response_model=list[QuantRecommendationRunView])
def list_recommendation_runs(session: Session = Depends(get_db_session)) -> list[QuantRecommendationRunView]:
    return QuantDeskService().list_runs(session)


@router.get("/portfolio-proposals/latest", response_model=QuantProposalView)
def get_latest_proposal(session: Session = Depends(get_db_session)) -> QuantProposalView:
    return QuantDeskService().get_proposal(session)


@router.get("/report-card", response_model=QuantReportCardView)
def get_report_card(window: str = "30d", session: Session = Depends(get_db_session)) -> QuantReportCardView:
    return QuantDeskService().get_report_card(session, window)


@router.get("/strategies", response_model=list[QuantStrategyView])
def list_strategies(session: Session = Depends(get_db_session)) -> list[QuantStrategyView]:
    return QuantDeskService().list_strategies(session)


@router.post("/strategies", response_model=QuantStrategyView)
def create_strategy(payload: QuantStrategyUpsert, session: Session = Depends(get_db_session)) -> QuantStrategyView:
    return QuantDeskService().upsert_strategy(session, payload.name, payload.dsl, payload.is_active)


@router.post("/strategies/preview")
def preview_strategy(payload: QuantStrategyUpsert) -> dict:
    return QuantDeskService().preview_strategy(payload.dsl)


@router.post("/backtests", response_model=QuantBacktestView)
def create_backtest(payload: QuantStrategyUpsert, session: Session = Depends(get_db_session)) -> QuantBacktestView:
    return QuantDeskService().run_backtest(session, None, payload.dsl)


@router.get("/paper/account", response_model=QuantPaperAccountView)
def get_paper_account(session: Session = Depends(get_db_session)) -> QuantPaperAccountView:
    return QuantDeskService().get_or_create_paper_account(session)


@router.post("/paper/orders", response_model=QuantPaperOrderView)
def post_paper_order(payload: QuantPaperOrderRequest, session: Session = Depends(get_db_session)) -> QuantPaperOrderView:
    return QuantDeskService().place_paper_order(session, payload.symbol, payload.side, payload.quantity, payload.confirmed)


@router.get("/decision-log", response_model=QuantDecisionLogView)
def get_decision_log(session: Session = Depends(get_db_session)) -> QuantDecisionLogView:
    return QuantDeskService().list_decisions(session)


@router.get("/copilot/tools", response_model=QuantCopilotToolsView)
def get_copilot_tools() -> QuantCopilotToolsView:
    return QuantDeskService().copilot_tools()
