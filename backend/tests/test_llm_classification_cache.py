"""分类结果缓存测试：相同内容第二次分类命中缓存、不再调用 LLM。"""

import hashlib
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


def test_classification_cache_hits_on_same_title_summary_despite_different_body() -> None:
    """缓存键改为 (title+summary+market):正文不同但标题/摘要/市场相同 => 命中缓存,不再发 LLM 请求。"""
    _clear_cache()
    provider = _provider()

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        return_value=CompletionResult(
            content='{"takeaway": "利好"}',
            prompt_tokens=10,
            completion_tokens=20,
        ),
    ) as mock_complete:
        first = provider.analyze_json(
            prompt="Title: 腾讯业绩超预期\nSummary: 二季度利润大增\nBody: " + "正文甲" * 200,
            title="腾讯业绩超预期",
            summary="二季度利润大增",
            market="hk",
        )
        second = provider.analyze_json(
            prompt="Title: 腾讯业绩超预期\nSummary: 二季度利润大增\nBody: 完全不同的正文乙",
            title="腾讯业绩超预期",
            summary="二季度利润大增",
            market="hk",
        )

    assert first == {"takeaway": "利好"}
    assert second == {"takeaway": "利好"}
    # 正文唯一但缓存键不含正文:第二次命中,只发一次 LLM 请求。
    assert mock_complete.call_count == 1


def test_classification_cache_miss_on_different_title_with_same_body() -> None:
    """title 不同(即使正文相同)视为不同内容,各自调用 LLM。"""
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
        first = provider.analyze_json(prompt="same body", title="标题一", summary="s", market="hk")
        second = provider.analyze_json(prompt="same body", title="标题二", summary="s", market="hk")

    assert first == {"n": 1}
    assert second == {"n": 2}
    assert mock_complete.call_count == 2


def test_compute_classification_fields_hash_normalizes_and_distinguishes_market() -> None:
    from app.services.llm_providers import compute_classification_fields_hash

    assert compute_classification_fields_hash(" 腾讯  业绩 ", "大增", "hk") == compute_classification_fields_hash(
        "腾讯 业绩", "大增", "hk"
    )
    assert compute_classification_fields_hash("腾讯业绩", "大增", "hk") != compute_classification_fields_hash(
        "腾讯业绩", "大增", "us"
    )


def test_compute_classification_fields_hash_default_scope_is_backward_compatible() -> None:
    """未传 scope 时哈希必须与旧签名(无 scope 参数)完全一致,避免作废存量选股缓存。"""
    from app.services.llm_providers import compute_classification_fields_hash

    # 旧行为快照:未加 scope 参数前, (title, summary, market) 的已知哈希值。
    legacy_hash = hashlib.sha256("腾讯业绩\x1f大增\x1fhk".encode()).hexdigest()
    assert compute_classification_fields_hash("腾讯业绩", "大增", "hk") == legacy_hash
    assert compute_classification_fields_hash("腾讯业绩", "大增", "hk", scope=None) == legacy_hash


def test_compute_classification_fields_hash_scope_distinguishes_same_fields() -> None:
    """相同 (title, summary, market) 但不同 scope(如情绪分类 vs 选股分析) => 不同缓存键。"""
    from app.services.llm_providers import compute_classification_fields_hash

    news_analysis_key = compute_classification_fields_hash("腾讯业绩", "大增", "hk")
    sentiment_key = compute_classification_fields_hash("腾讯业绩", "大增", "hk", scope="sentiment")
    assert news_analysis_key != sentiment_key


def test_analyze_json_cache_scope_isolates_sentiment_from_news_analysis() -> None:
    """情绪分类(cache_scope='sentiment')与选股分析(默认 scope)对同一新闻不应互相命中缓存。"""
    _clear_cache()
    provider = _provider()

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        side_effect=[
            CompletionResult(
                content='{"top_pick": "AAPL", "summary": "s1"}', prompt_tokens=1, completion_tokens=1
            ),
            CompletionResult(
                content='{"sentiment_label": "positive", "sentiment_score": 0.5}',
                prompt_tokens=1,
                completion_tokens=1,
            ),
        ],
    ) as mock_complete:
        news_analysis_result = provider.analyze_json(
            prompt="stock analysis prompt", title="腾讯业绩超预期", summary="二季度利润大增", market="hk"
        )
        sentiment_result = provider.analyze_json(
            prompt="sentiment prompt",
            title="腾讯业绩超预期",
            summary="二季度利润大增",
            market="hk",
            cache_scope="sentiment",
        )

    assert news_analysis_result == {"top_pick": "AAPL", "summary": "s1"}
    assert sentiment_result == {"sentiment_label": "positive", "sentiment_score": 0.5}
    # 两条路径各自的缓存键不同,LLM 各被调用一次(未互相命中对方缓存)。
    assert mock_complete.call_count == 2


def test_analyze_json_default_system_prompt_unchanged_for_news_analysis() -> None:
    """未传 system_prompt 时(选股分析路径),system 消息内容与改造前完全一致。"""
    _clear_cache()
    provider = _provider()

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        return_value=CompletionResult(content='{"top_pick": "AAPL"}', prompt_tokens=1, completion_tokens=1),
    ) as mock_complete:
        provider.analyze_json(prompt="stock analysis prompt")

    _, kwargs = mock_complete.call_args
    system_message = kwargs["messages"][0]
    assert system_message["role"] == "system"
    assert "top_pick, candidates, summary, risk_notes, sentiment, context_limitations" in system_message["content"]


def test_analyze_json_custom_system_prompt_is_used_when_provided() -> None:
    """传入 system_prompt 时(情绪分类路径),必须使用调用方传入的 system prompt,而非硬编码选股 schema。"""
    _clear_cache()
    provider = _provider()
    custom_prompt = "Return JSON only with keys: sentiment_label, sentiment_score."

    with patch.object(
        OpenAICompatibleProvider,
        "complete",
        return_value=CompletionResult(
            content='{"sentiment_label": "neutral"}', prompt_tokens=1, completion_tokens=1
        ),
    ) as mock_complete:
        provider.analyze_json(prompt="sentiment prompt", system_prompt=custom_prompt)

    _, kwargs = mock_complete.call_args
    system_message = kwargs["messages"][0]
    assert system_message["role"] == "system"
    assert system_message["content"] == custom_prompt
