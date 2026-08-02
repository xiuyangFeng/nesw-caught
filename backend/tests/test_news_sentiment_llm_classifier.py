"""纯 LLM 情绪分类器测试：mock build_provider，不联网。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_llm_classifier import (
    SENTIMENT_EVAL_CACHE_SCOPE,
    SENTIMENT_EVAL_SYSTEM_PROMPT,
    NewsSentimentLLMClassifier,
)


def _sample(**overrides) -> SentimentGoldSample:
    payload = {
        "sample_id": "s1",
        "text": "fallback text",
        "sentiment_label": "positive",
        "title": "标题",
        "summary": "摘要",
        "body": "正文",
        "market": "hk",
    }
    payload.update(overrides)
    return SentimentGoldSample(**payload)


def _fake_config() -> SimpleNamespace:
    # analyze_json 的调用被整体 mock，config 本身内容无关紧要。
    return SimpleNamespace(provider_name="openai_compatible", model_name="deepseek-chat")


def _rule_fallback_calls():
    calls: list[SentimentGoldSample] = []

    def fallback(sample: SentimentGoldSample) -> str:
        calls.append(sample)
        return "neutral"

    return fallback, calls


def test_classify_returns_llm_label_and_uses_dedicated_system_prompt_and_scope() -> None:
    fallback, calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)
    sample = _sample()

    fake_provider = SimpleNamespace(
        analyze_json=lambda **kwargs: {"sentiment_label": "negative", "sentiment_score": -0.6}
    )
    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        return_value=fake_provider,
    ) as mock_build_provider:
        with patch.object(
            fake_provider, "analyze_json", wraps=fake_provider.analyze_json
        ) as mock_analyze_json:
            label = classifier.classify(sample)

    assert label == "negative"
    assert classifier.fallback_count == 0
    assert classifier.call_count == 1
    assert calls == []  # 未走回退

    mock_build_provider.assert_called_once_with(classifier.config)
    _, kwargs = mock_analyze_json.call_args
    assert kwargs["title"] == "标题"
    assert kwargs["summary"] == "摘要"
    assert kwargs["market"] == "hk"
    assert kwargs["system_prompt"] == SENTIMENT_EVAL_SYSTEM_PROMPT
    assert kwargs["cache_scope"] == SENTIMENT_EVAL_CACHE_SCOPE


def test_classify_falls_back_to_rule_on_llm_exception_and_counts() -> None:
    fallback, calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)
    sample = _sample()

    fake_provider = SimpleNamespace(analyze_json=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        return_value=fake_provider,
    ):
        label = classifier.classify(sample)

    assert label == "neutral"
    assert classifier.fallback_count == 1
    assert classifier.call_count == 1
    assert calls == [sample]


def test_classify_falls_back_when_payload_missing_label() -> None:
    fallback, calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)
    sample = _sample()

    fake_provider = SimpleNamespace(analyze_json=lambda **kwargs: {"sentiment_score": 0.1})
    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        return_value=fake_provider,
    ):
        label = classifier.classify(sample)

    assert label == "neutral"
    assert classifier.fallback_count == 1
    assert calls == [sample]


def test_classify_falls_back_when_payload_label_is_invalid() -> None:
    fallback, calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)
    sample = _sample()

    fake_provider = SimpleNamespace(
        analyze_json=lambda **kwargs: {"sentiment_label": "bullish", "sentiment_score": 0.9}
    )
    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        return_value=fake_provider,
    ):
        label = classifier.classify(sample)

    assert label == "neutral"
    assert classifier.fallback_count == 1
    assert calls == [sample]


def test_classify_falls_back_when_payload_is_not_a_dict() -> None:
    fallback, calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)
    sample = _sample()

    fake_provider = SimpleNamespace(analyze_json=lambda **kwargs: "not-json")
    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        return_value=fake_provider,
    ):
        label = classifier.classify(sample)

    assert label == "neutral"
    assert classifier.fallback_count == 1
    assert calls == [sample]


def test_multiple_samples_accumulate_call_and_fallback_counts() -> None:
    fallback, _calls = _rule_fallback_calls()
    classifier = NewsSentimentLLMClassifier(config=_fake_config(), rule_fallback=fallback)

    good_provider = SimpleNamespace(
        analyze_json=lambda **kwargs: {"sentiment_label": "positive", "sentiment_score": 0.5}
    )
    bad_provider = SimpleNamespace(analyze_json=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with patch(
        "app.services.news_sentiment_llm_classifier.build_provider",
        side_effect=[good_provider, bad_provider, good_provider],
    ):
        labels = [classifier.classify(_sample(sample_id=f"s{i}")) for i in range(3)]

    assert labels == ["positive", "neutral", "positive"]
    assert classifier.call_count == 3
    assert classifier.fallback_count == 1
