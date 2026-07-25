import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.core.auth import init_app_token
from app.core.config import Settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def enable_token_verification(monkeypatch):
    # 覆盖测试套件默认关闭的鉴权开关，强制在测试运行期间启用 Token 校验
    enforced = Settings(verify_app_token=True)
    monkeypatch.setattr(auth, "get_settings", lambda: enforced)
    yield


def test_request_without_token_returns_401():
    # 访问需要保护的路由，不带 Header 应该返回 401
    response = client.get("/api/llm/config")
    assert response.status_code == 401
    assert "Token is missing" in response.json()["detail"]


def test_request_with_invalid_token_returns_401():
    # 访问需要保护的路由，带错的 Header 应该返回 401
    response = client.get("/api/llm/config", headers={"X-App-Token": "wrong-token-value"})
    assert response.status_code == 401
    assert "Token is invalid" in response.json()["detail"]


def test_request_with_valid_token_succeeds():
    # 访问需要保护的路由，带正确的 Header 应该成功
    token = init_app_token()
    response = client.get("/api/llm/config", headers={"X-App-Token": token})
    # 只要不返回 401，就证明通过了认证（由于没配置默认 LLM 可能会返回 200 configured=False）
    assert response.status_code == 200


def test_health_check_bypasses_token_verification():
    # 访问放行路由 /api/health，不需要 X-App-Token 应该直接通过返回 200
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_root_doc_paths_are_not_registered(path):
    # 安全评审发现：FastAPI(docs_url=..., openapi_url=...) 挂在 app 根路径下的
    # 内置文档端点不经过 api_router，会绕过 verify_app_token。修复为关闭内置
    # 端点、改在 api_router 下提供等价路由，这里确认根路径版本确实已下线。
    response = client.get(path)
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/api/docs", "/api/redoc", "/api/openapi.json"])
def test_doc_endpoints_require_token(path):
    response = client.get(path)
    assert response.status_code == 401


def test_doc_endpoints_accessible_with_valid_token():
    token = init_app_token()
    headers = {"X-App-Token": token}

    openapi_response = client.get("/api/openapi.json", headers=headers)
    assert openapi_response.status_code == 200
    assert "openapi" in openapi_response.json()

    docs_response = client.get("/api/docs", headers=headers)
    assert docs_response.status_code == 200
    assert "swagger" in docs_response.text.lower()

    redoc_response = client.get("/api/redoc", headers=headers)
    assert redoc_response.status_code == 200


def test_docs_page_forwards_query_token_into_embedded_openapi_url():
    # /api/docs 靠浏览器直接导航打开，无法附加自定义请求头，因此和 SSE 一样
    # 允许 ?token= 传递；页面内嵌 JS 会再单独请求 openapi_url，这个 URL 必须
    # 把 token 带上，否则页面能打开但 schema 加载会因为 401 而失败。
    token = init_app_token()
    response = client.get(f"/api/docs?token={token}")
    assert response.status_code == 200
    assert f"token={token}" in response.text
