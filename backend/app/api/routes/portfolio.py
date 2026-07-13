from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.portfolio import PortfolioSummaryView
from app.services.portfolio_service import PortfolioService

router = APIRouter()


@router.get("", response_model=PortfolioSummaryView)
def get_portfolio_summary(session: Session = Depends(get_db_session)) -> PortfolioSummaryView:
    """组合汇总：总市值 / 总盈亏 + 按仓位价值加权的“最该看”新闻。"""
    return PortfolioService().build_summary(session)
