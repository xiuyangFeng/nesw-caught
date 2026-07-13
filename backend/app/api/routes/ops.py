"""运维健康看板路由。

``GET /ops/health`` 返回 :func:`build_ops_health` 的按需聚合结果。
鉴权由 ``app.api.router`` 上挂载的 ``verify_app_token`` 依赖自动继承。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.ops import OpsHealthResponse
from app.services.ops_health import build_ops_health

router = APIRouter()


@router.get("/health", response_model=OpsHealthResponse)
def ops_health(session: Session = Depends(get_db_session)) -> OpsHealthResponse:
    return build_ops_health(session)
