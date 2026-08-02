"""_llm_refine bug fixes:

1. 必须使用与其 user prompt schema 匹配的专用情绪 system prompt(不能复用
   analyze_json 默认的选股分析 system prompt),否则模型大概率按错误 schema
   返回、导致 sentiment_label 等字段为 None 静默回退规则结果。
2. 必须传 cache_scope="sentiment",与选股分析(news_analysis.py)的缓存隔离。
3. LLM 返回缺 key / 类型错误时仍保留现有回退行为，但不再完全静默：
   记 warning 日志 + 失败计数。
"""

import logging

import pytest

from app.db.session import SessionLocal
from app.services import news_signal_classifier as classifier_module
from app.services.news_signal_classifier import ClassificationResult, NewsSignalClassifier


class _RecordingProvider:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.calls: list[dict[str, object]] = []

    def analyze_json(
        self,
        *,
        prompt: str,
        title=None,
        summary=None,
        market=None,
        system_prompt=None,
        cache_scope=None,
    ) -> object:
        self.calls.append(
            {
                "prompt": prompt,
                "title": title,
                "summary": summary,
                "market": market,
                "system_prompt": system_prompt,
                "cache_scope": cache_scope,
            }
        )
        return self._payload


def _baseline() -> ClassificationResult:
    return ClassificationResult(
        sentiment_label="neutral",
        sentiment_score=0.0,
        signal_confidence=0.4,
        keywords=["ai"],
        topic_key="ai",
        summary="s",
        classifier_type="rule",
    )


def test_llm_refine_passes_sentiment_cache_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        provider = _RecordingProvider({"sentiment_label": "positive", "sentiment_score": 0.5})
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        classifier._llm_refine(_baseline(), title="t", summary="s", body="b")

    assert provider.calls[0]["cache_scope"] == "sentiment"


def test_llm_refine_uses_dedicated_sentiment_system_prompt_matching_user_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """system prompt 必须与 user prompt 要求的 key 集合一致，且不是选股分析的默认 schema。"""
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        provider = _RecordingProvider({"sentiment_label": "positive", "sentiment_score": 0.5})
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        classifier._llm_refine(_baseline(), title="t", summary="s", body="b")

    system_prompt = provider.calls[0]["system_prompt"]
    assert system_prompt is not None
    # 与选股分析默认 schema 的 key 不同，不能复用硬编码的选股 prompt。
    assert "top_pick" not in system_prompt
    assert "context_limitations" not in system_prompt
    # 与情绪分类 user prompt 要求的 key 一致。
    for key in (
        "sentiment_label",
        "sentiment_score",
        "summary",
        "keywords",
        "topic_title_hint",
        "takeaway",
    ):
        assert key in system_prompt


def test_llm_refine_still_falls_back_but_logs_and_counts_on_invalid_payload_type(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        provider = _RecordingProvider(["not", "a", "dict"])
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        baseline = _baseline()
        with caplog.at_level(logging.WARNING, logger=classifier_module.__name__):
            result = classifier._llm_refine(baseline, title="t", summary="s", body="b")

    # 回退行为不变：非 dict payload 时返回规则基线结果。
    assert result.sentiment_label == baseline.sentiment_label
    assert result.classifier_type == "rule"
    # 但不再完全静默：有 warning 日志 + 失败计数递增。
    assert any("sentiment" in record.message.lower() for record in caplog.records)
    assert classifier.llm_refine_failure_count == 1


def test_llm_refine_still_falls_back_but_logs_and_counts_on_missing_sentiment_label(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        # summary 存在但 sentiment_label 缺失(schema 不匹配时最典型的静默失效场景)。
        provider = _RecordingProvider({"summary": "some summary", "risk_notes": "x"})
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        baseline = _baseline()
        with caplog.at_level(logging.WARNING, logger=classifier_module.__name__):
            result = classifier._llm_refine(baseline, title="t", summary="s", body="b")

    assert result.sentiment_label == baseline.sentiment_label
    assert classifier.llm_refine_failure_count == 1
    assert len(caplog.records) >= 1


def test_llm_refine_failure_count_accumulates_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        provider = _RecordingProvider({})  # 缺 sentiment_label
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        classifier._llm_refine(_baseline(), title="t", summary="s", body="b")
        classifier._llm_refine(_baseline(), title="t2", summary="s2", body="b2")

    assert classifier.llm_refine_failure_count == 2


def test_llm_refine_does_not_count_success_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        monkeypatch.setattr(classifier.config_repository, "get_active", lambda: object())
        provider = _RecordingProvider(
            {
                "sentiment_label": "negative",
                "sentiment_score": -0.6,
                "summary": "s",
                "keywords": ["a"],
                "topic_title_hint": "hint",
                "takeaway": "利空",
            }
        )
        monkeypatch.setattr(classifier_module, "build_provider", lambda _config: provider)

        result = classifier._llm_refine(_baseline(), title="t", summary="s", body="b")

    assert result.sentiment_label == "negative"
    assert classifier.llm_refine_failure_count == 0
