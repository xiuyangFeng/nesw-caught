from __future__ import annotations

import json

from sqlalchemy import inspect, text

from app.db.session import SessionLocal, engine
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.digest_service import (
    SECTION_OVERNIGHT,
    SECTION_RISK,
    SECTION_SENTIMENT,
    SECTION_WATCHLIST,
    generate_digest,
    get_latest_digest,
    reset_latest_digest,
)


def _cleanup_llm_config() -> None:
    inspector = inspect(engine)
    if "llm_provider_config" not in inspector.get_table_names():
        return
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM llm_provider_config"))


def _insert_default_llm_config() -> None:
    with SessionLocal() as session:
        LLMProviderConfigRepository(session).upsert_config(
            provider_name="openai_compatible",
            display_name="Digest Test",
            base_url="https://example-llm.test/v1",
            model_name="deepseek-chat",
            api_key="sk-real-digest-secret",
            is_active=True,
            is_default=True,
        )
        session.commit()


def _fake_llm_builder(payload: dict[str, str]):
    def builder(_config):
        class FakeProvider:
            def complete(self, *, messages, response_format=None, operation_type="chat"):
                from app.services.llm_providers import CompletionResult

                assert operation_type == "digest"
                assert response_format == {"type": "json_object"}
                return CompletionResult(content=json.dumps(payload, ensure_ascii=False))

        return FakeProvider()

    return builder


def test_generate_digest_uses_llm_and_updates_singleton() -> None:
    _cleanup_llm_config()
    reset_latest_digest()
    _insert_default_llm_config()

    payload = {
        "overnight": "隔夜美股科技股走强，重点关注 AI 算力链。",
        "watchlist": "自选股腾讯出现利好新闻。",
        "sentiment": "整体情绪偏多。",
        "risk": "留意美联储议息带来的波动风险。",
    }

    with SessionLocal() as session:
        digest = generate_digest("all", session, provider_builder=_fake_llm_builder(payload))

    assert digest.generated_by == "llm"
    assert digest.model_name == "deepseek-chat"
    assert digest.market_scope == "all"
    assert digest.generated_at.tzinfo is not None

    bodies = {section.title: section.body for section in digest.sections}
    assert [s.title for s in digest.sections] == [
        SECTION_OVERNIGHT,
        SECTION_WATCHLIST,
        SECTION_SENTIMENT,
        SECTION_RISK,
    ]
    assert bodies[SECTION_OVERNIGHT] == payload["overnight"]
    assert bodies[SECTION_WATCHLIST] == payload["watchlist"]
    assert bodies[SECTION_SENTIMENT] == payload["sentiment"]
    assert bodies[SECTION_RISK] == payload["risk"]

    # 单例被更新为最新一份。
    assert get_latest_digest() is digest


def test_generate_digest_degrades_to_rule_based_without_config() -> None:
    _cleanup_llm_config()
    reset_latest_digest()

    with SessionLocal() as session:
        digest = generate_digest("hk", session)

    assert digest.generated_by == "rule"
    assert digest.model_name is None
    assert digest.market_scope == "hk"
    assert len(digest.sections) == 4
    assert all(section.body for section in digest.sections)
    assert get_latest_digest() is digest


def test_generate_digest_degrades_when_llm_raises() -> None:
    _cleanup_llm_config()
    reset_latest_digest()
    _insert_default_llm_config()

    def failing_builder(_config):
        class FailingProvider:
            def complete(self, *, messages, response_format=None, operation_type="chat"):
                from app.services.llm_providers import LLMProviderError

                raise LLMProviderError("provider unreachable")

        return FailingProvider()

    with SessionLocal() as session:
        # 关键：LLM 抛错时不得向上冒泡，必须优雅降级。
        digest = generate_digest("us", session, provider_builder=failing_builder)

    assert digest.generated_by == "rule"
    assert digest.model_name is None
    assert len(digest.sections) == 4
    assert get_latest_digest() is digest
