from fastapi import APIRouter

from app.api.routes import health, llm, market, news, stream, topics, watchlist, x_monitor

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(topics.router, prefix="/topics", tags=["topics"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(x_monitor.router, prefix="/x", tags=["x-monitor"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
