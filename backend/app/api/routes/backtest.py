"""信号有效性回测路由（纯读汇总）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.backtest import BacktestSummaryView
from app.services.signal_backtest import SignalBacktestService

router = APIRouter()


@router.get("", response_model=BacktestSummaryView)
def get_backtest_summary(
    market: str | None = Query(default=None, description="市场过滤：hk/us/cn，缺省为全部"),
    window_days: int = Query(default=30, ge=1, le=365, description="回看窗口天数"),
    horizon: str = Query(default="1d", description="前视时间窗，如 1h/4h/1d"),
    session: Session = Depends(get_db_session),
) -> BacktestSummaryView:
    service = SignalBacktestService(session)
    try:
        summary = service.run(market=market, window_days=window_days, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BacktestSummaryView.model_validate(summary)
