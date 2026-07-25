from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from app.api.routes import (
    backtest,
    calendar,
    digest,
    eval,
    health,
    llm,
    market,
    news,
    notify,
    ops,
    portfolio,
    research,
    stream,
    topics,
    watchlist,
    x_monitor,
)
from app.core.auth import verify_app_token
from app.core.config import get_settings

api_router = APIRouter(dependencies=[Depends(verify_app_token)])
api_router.include_router(eval.router, prefix="/eval", tags=["eval"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(digest.router, prefix="/digest", tags=["digest"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(notify.router, prefix="/notify", tags=["notify"])
api_router.include_router(topics.router, prefix="/topics", tags=["topics"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(x_monitor.router, prefix="/x", tags=["x-monitor"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])


# API 文档端点原本由 FastAPI(docs_url=..., openapi_url=...) 直接挂在 app 上，
# 不经过 api_router，因而绕过了 verify_app_token（详见安全评审记录）。
# 改为挂在 api_router 下，自动继承鉴权依赖。
@api_router.get("/openapi.json", include_in_schema=False)
def get_openapi_schema(request: Request) -> JSONResponse:
    return JSONResponse(request.app.openapi())


def _build_openapi_url(request: Request, settings: Any) -> str:
    # Swagger UI / ReDoc 页面加载后，会用浏览器内嵌 JS 再单独发一次请求取
    # openapi.json，这次请求不会带上打开本页时用的请求头/query token，所以
    # 要把已经通过 verify_app_token 校验的 token 显式带进 openapi_url。
    openapi_url = f"{settings.api_prefix}/openapi.json"
    token = request.headers.get("x-app-token") or request.query_params.get("token")
    if token:
        openapi_url = f"{openapi_url}?token={token}"
    return openapi_url


@api_router.get("/docs", include_in_schema=False)
def get_swagger_docs(request: Request) -> Any:
    settings = get_settings()
    return get_swagger_ui_html(
        openapi_url=_build_openapi_url(request, settings),
        title=f"{settings.app_name} - Swagger UI",
    )


@api_router.get("/redoc", include_in_schema=False)
def get_redoc_docs(request: Request) -> Any:
    settings = get_settings()
    return get_redoc_html(
        openapi_url=_build_openapi_url(request, settings),
        title=f"{settings.app_name} - ReDoc",
    )
