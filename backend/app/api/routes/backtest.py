"""信号有效性回测路由（纯读汇总 + 校准落盘）。

回测本身（`SignalBacktestService`）保持纯读；置信度校准的构建与落盘（工作块
E5）放在路由层完成——每次回测顺带用本次 `score_buckets` 重算校准映射并写入
`backend/data/research/sentiment_calibration.json`，写失败不影响回测响应本身
（仅日志告警，calibration 字段仍返回本次内存计算结果）。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.backtest import BacktestSummaryView
from app.services.sentiment_calibration import build_calibration, save_calibration
from app.services.signal_backtest import SignalBacktestService

logger = logging.getLogger(__name__)

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

    calibration = build_calibration(summary)
    try:
        save_calibration(calibration)
    except OSError:
        logger.warning("failed to persist sentiment_calibration.json", exc_info=True)
    summary["calibration"] = calibration
    return BacktestSummaryView.model_validate(summary)
