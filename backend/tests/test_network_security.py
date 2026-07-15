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
