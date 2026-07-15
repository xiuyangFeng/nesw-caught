import logging
import os
import secrets

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_app_token: str | None = None

def get_token_file_path() -> str:
    # 动态定位 data 目录，与 crypto.py 保持一致
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, ".app_token")

def init_app_token() -> str:
    global _app_token
    if _app_token is not None:
        return _app_token

    token_file = get_token_file_path()
    if os.path.exists(token_file):
        try:
            with open(token_file, encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                _app_token = token
                logger.info("Loaded app token from %s", token_file)
                return _app_token
        except Exception as exc:
            logger.warning("Failed to load app token file: %s. Re-generating...", exc)

    # 首次启动生成新 Token
    try:
        new_token = secrets.token_hex(32)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(new_token)
        try:
            os.chmod(token_file, 0o600)
        except Exception:
            logger.warning("Failed to set chmod 600 on app token file")
        _app_token = new_token
        logger.info("Generated new app token and saved to %s", token_file)
        return _app_token
    except Exception as exc:
        logger.error("Failed to generate app token: %s", exc)
        # 兜底在内存中临时生成，不至于服务崩溃但无法持久化
        temp_token = secrets.token_hex(32)
        _app_token = temp_token
        return _app_token

def verify_app_token(
    request: Request,
    x_app_token: str | None = Header(default=None, alias="X-App-Token")
) -> None:
    # 放行健康检查相关的只读 API，便于探活监控
    if request.url.path.startswith("/api/health"):
        return

    # 通过显式配置控制是否校验 App Token（测试套件在 conftest.py 中全局关闭，
    # 生产默认开启，见 Settings.verify_app_token / 环境变量 VERIFY_APP_TOKEN）
    if not get_settings().verify_app_token:
        return

    # 获取/初始化本机的 App Token
    expected_token = init_app_token()

    provided_token = x_app_token
    # SSE 流路由特殊处理：浏览器原生 EventSource 无法携带自定义请求头，
    # 允许通过 query 参数 token 传递 App Token（仅限 /api/stream/ 下的路由）
    if not provided_token and request.url.path.startswith("/api/stream/"):
        provided_token = request.query_params.get("token")

    if not provided_token:
        logger.warning("Request to %s blocked: App Token is missing", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App Token is missing. Access denied."
        )

    if not secrets.compare_digest(provided_token, expected_token):
        logger.warning("Request to %s blocked: App Token is invalid", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App Token is invalid. Access denied."
        )
