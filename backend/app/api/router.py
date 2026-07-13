from fastapi import APIRouter, Depends

from app.api.routes import backtest, health, llm, market, news, notify, ops, stream, topics, watchlist, x_monitor
from app.core.auth import verify_app_token

api_router = APIRouter(dependencies=[Depends(verify_app_token)])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(notify.router, prefix="/notify", tags=["notify"])
api_router.include_router(topics.router, prefix="/topics", tags=["topics"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(x_monitor.router, prefix="/x", tags=["x-monitor"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
