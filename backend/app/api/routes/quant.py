from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.quant import (
    QuantDataStatusView,
    QuantFundFlowView,
    QuantRadarView,
    QuantRecommendationLatestView,
    QuantRunRequest,
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


@router.get("/radar", response_model=QuantRadarView)
def get_quant_radar(session: Session = Depends(get_db_session)) -> QuantRadarView:
    return QuantDeskService().get_radar(session)


@router.get("/symbols/{symbol}/fund-flow", response_model=QuantFundFlowView)
def get_symbol_fund_flow(symbol: str) -> QuantFundFlowView:
    return QuantDeskService().get_fund_flow(symbol)
