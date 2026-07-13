"""LLM 成本治理测试：单价换算、月度预算对比、无单价降级为 null。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.llm_provider_config import LLMProviderConfig
from app.models.llm_token_usage import LLMTokenUsage
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import log_token_usage


def _reset() -> None:
    with SessionLocal() as session:
        session.query(LLMTokenUsage).delete()
        session.query(LLMProviderConfig).delete()
        session.commit()


def _priced_config(
    *,
    model_name: str,
    input_price: float | None,
    output_price: float | None,
    budget: float | None = None,
    is_default: bool = True,
) -> None:
    with SessionLocal() as session:
        LLMProviderConfigRepository(session).upsert_config(
            provider_name="openai_compatible",
            display_name="Cost Test",
            base_url="https://api.cost-test.com/v1",
            model_name=model_name,
            api_key="sk-cost-test",
            is_active=True,
            is_default=is_default,
            input_price_per_1k=input_price,
            output_price_per_1k=output_price,
            monthly_budget_usd=budget,
        )
        session.commit()


def test_stats_converts_tokens_to_usd_cost() -> None:
    _reset()
    _priced_config(
        model_name="priced-model",
        input_price=0.001,   # $/1K input tokens
        output_price=0.002,  # $/1K output tokens
        budget=None,
    )
    log_token_usage(
        model_name="priced-model",
        prompt_tokens=1000,
        completion_tokens=500,
        operation_type="analysis",
    )

    client = TestClient(app)
    res = client.get("/api/llm/stats")
    assert res.status_code == 200
    data = res.json()

    model = next(m for m in data["models"] if m["model_name"] == "priced-model")
    # 1000/1000*0.001 + 500/1000*0.002 = 0.001 + 0.001 = 0.002
    assert model["cost_available"] is True
    assert model["cost_usd"] == pytest.approx(0.002)
    assert model["input_price_per_1k"] == pytest.approx(0.001)
    assert model["output_price_per_1k"] == pytest.approx(0.002)

    assert data["overall"]["cost_available"] is True
    assert data["overall"]["cost_usd"] == pytest.approx(0.002)


def test_stats_cost_is_null_when_price_missing() -> None:
    _reset()
    # 未给任何模型配置单价。
    log_token_usage(
        model_name="unpriced-model",
        prompt_tokens=800,
        completion_tokens=200,
        operation_type="analysis",
    )

    client = TestClient(app)
    data = client.get("/api/llm/stats").json()

    model = next(m for m in data["models"] if m["model_name"] == "unpriced-model")
    assert model["cost_available"] is False
    assert model["cost_usd"] is None
    assert data["overall"]["cost_available"] is False
    assert data["overall"]["cost_usd"] is None


def test_stats_budget_over_budget_flag() -> None:
    _reset()
    _priced_config(
        model_name="budget-model",
        input_price=0.01,
        output_price=0.02,
        budget=0.001,  # 极小预算，必然超支
    )
    log_token_usage(
        model_name="budget-model",
        prompt_tokens=1000,
        completion_tokens=1000,
        operation_type="analysis",
    )

    client = TestClient(app)
    data = client.get("/api/llm/stats").json()

    budget = data["budget"]
    # 0.01 + 0.02 = 0.03 花费 > 0.001 预算
    assert budget["budget_available"] is True
    assert budget["monthly_budget_usd"] == pytest.approx(0.001)
    assert budget["month_cost_usd"] == pytest.approx(0.03)
    assert budget["over_budget"] is True
    assert budget["usage_ratio"] is not None and budget["usage_ratio"] > 1.0


def test_stats_budget_not_configured() -> None:
    _reset()
    _priced_config(
        model_name="nobudget-model",
        input_price=0.001,
        output_price=0.001,
        budget=None,
    )
    log_token_usage(
        model_name="nobudget-model",
        prompt_tokens=100,
        completion_tokens=100,
        operation_type="analysis",
    )

    client = TestClient(app)
    data = client.get("/api/llm/stats").json()

    budget = data["budget"]
    assert budget["budget_available"] is False
    assert budget["monthly_budget_usd"] is None
    assert budget["over_budget"] is False
