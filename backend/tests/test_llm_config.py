from sqlalchemy import inspect, text

from app.db.session import engine
from fastapi.testclient import TestClient

from app.main import app


def _cleanup_llm_config_table() -> None:
    inspector = inspect(engine)
    if "llm_provider_config" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM llm_provider_config"))


def test_get_llm_config_returns_not_configured_when_missing() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    response = client.get("/api/llm/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["provider_name"] is None
    assert payload["model_name"] is None
    assert payload["base_url"] is None


def test_post_llm_config_persists_active_provider_without_exposing_raw_key() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    response = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["provider_name"] == "openai_compatible"
    assert payload["model_name"] == "deepseek-chat"
    assert payload["base_url"] == "https://example-llm.test/v1"
    assert payload["display_name"] == "OpenAI Compatible"
    assert payload["api_key_set"] is True
    assert payload["api_key"] == "sk-***cret"
    assert payload["api_key"] != "sk-test-secret"

    follow_up = client.get("/api/llm/config")

    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["configured"] is True
    assert follow_up_payload["provider_name"] == "openai_compatible"
    assert follow_up_payload["model_name"] == "deepseek-chat"
    assert follow_up_payload["api_key_set"] is True
    assert follow_up_payload["api_key"] == "sk-***cret"
    assert follow_up_payload["api_key"] != "sk-test-secret"


def test_post_llm_config_preserves_existing_key_when_update_omits_new_key() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    initial = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )
    assert initial.status_code == 200

    updated = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v2",
            "model_name": "deepseek-reasoner",
            "api_key": "",
        },
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["configured"] is True
    assert payload["model_name"] == "deepseek-reasoner"
    assert payload["base_url"] == "https://example-llm.test/v2"
    assert payload["api_key_set"] is True


def test_post_llm_config_normalizes_known_deepseek_typo_host() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    response = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "DeepSeek",
            "base_url": "https://api.deepssek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["base_url"] == "https://api.deepseek.com/v1"


def test_post_llm_config_requires_key_when_creating_first_config() -> None:
    _cleanup_llm_config_table()
    client = TestClient(app)

    response = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "api key is required when creating the first llm config"
