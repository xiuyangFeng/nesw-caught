"""分类结果缓存测试：相同内容第二次分类命中缓存、不再调用 LLM。"""

from types import SimpleNamespace
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models.llm_classification_cache import LLMClassificationCache
from app.repositories.llm_classification_cache_repository import (
    LLMClassificationCacheRepository,
)
from app.services.llm_providers import (
    CompletionResult,
    OpenAICompatibleProvider,
    compute_classification_hash,
)


def _clear_cache() -> None:
    with SessionLocal() as session:
        session.query(LLMClassificationCache).delete()
        session.commit()


def _provider(model_name: str = "cache-test-model") -> OpenAICompatibleProvider:
    # analyze_json 只用到 config.model_name 与被 mock 的 complete()，
    # 因此使用轻量的 SimpleNamespace 即可，无需真实 provider 配置。
    return OpenAICompatibleProvider(SimpleNamespace(model_name=model_name))


def test_classification_cache_hits_second_call_and_skips_llm() -> None:
    _clear_cache()
    provider = _provider()

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        return_value=CompletionResult(
            content='{"sentiment_label": "positive"}',
            prompt_tokens=10,
            completion_tokens=20,
        ),
    ) as mock_complete:
        first = provider.analyze_json(prompt="  Apple beats  earnings  ")
        second = provider.analyze_json(prompt="Apple beats earnings")  # 归一化后同内容

    assert first == {"sentiment_label": "positive"}
    assert second == {"sentiment_label": "positive"}
    # 第二次归一化后 hash 相同，命中缓存，LLM 只被调用一次。
    assert mock_complete.call_count == 1

    # 缓存已落库，且记录了模型名。
    content_hash = compute_classification_hash("Apple beats earnings")
    with SessionLocal() as session:
        entry = LLMClassificationCacheRepository(session).get_by_hash(content_hash)
        assert entry is not None
        assert entry.model_name == "cache-test-model"


def test_classification_cache_disabled_does_not_cache() -> None:
    _clear_cache()
    provider = _provider()

    with patch(
        "app.services.llm_providers.get_settings",
        return_value=SimpleNamespace(llm_classification_cache_enabled=False),
    ):
        with patch.object(
            OpenAICompatibleProvider,
            "complete",
            return_value=CompletionResult(
                content='{"sentiment_label": "neutral"}',
                prompt_tokens=5,
                completion_tokens=5,
            ),
        ) as mock_complete:
            provider.analyze_json(prompt="same content twice")
            provider.analyze_json(prompt="same content twice")

    # 开关关闭：每次都真正调用 LLM，且不写缓存。
    assert mock_complete.call_count == 2
    content_hash = compute_classification_hash("same content twice")
    with SessionLocal() as session:
        entry = LLMClassificationCacheRepository(session).get_by_hash(content_hash)
        assert entry is None


def test_classification_cache_miss_on_different_content() -> None:
    _clear_cache()
    provider = _provider()

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        side_effect=[
            CompletionResult(content='{"n": 1}', prompt_tokens=1, completion_tokens=1),
            CompletionResult(content='{"n": 2}', prompt_tokens=1, completion_tokens=1),
        ],
    ) as mock_complete:
        first = provider.analyze_json(prompt="content A")
        second = provider.analyze_json(prompt="content B")

    assert first == {"n": 1}
    assert second == {"n": 2}
    assert mock_complete.call_count == 2
