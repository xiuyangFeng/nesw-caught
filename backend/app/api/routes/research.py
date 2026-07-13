"""个股 AI 综合研判路由（本地语料 RAG，结构化研报）。

GET /research/stock/{symbol} —— 返回某只股票近 N 天命中新闻 + 价格走势综合而成的
结构化研报。研判服务内部对 LLM 不可用/失败做优雅降级，路由本身不需处理异常。
鉴权由上层 api_router 的 verify_app_token 依赖统一继承。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.stock_research import StockResearchReport
from app.services.stock_research_synthesis import synthesize_stock_research

router = APIRouter()


@router.get("/stock/{symbol}", response_model=StockResearchReport)
def get_stock_research(
    symbol: str,
    lookback_days: int = Query(7, ge=1, le=30),
    session: Session = Depends(get_db_session),
) -> StockResearchReport:
    return synthesize_stock_research(symbol, session, lookback_days=lookback_days)
