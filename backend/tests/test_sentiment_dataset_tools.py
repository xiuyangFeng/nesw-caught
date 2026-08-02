"""backend/scripts/{sample,annotate,review}_sentiment_dataset*.py 的单元测试。

情绪评测金标数据集工具链（工作块 C）。全部 mock DB / LLM，不联网、不落真实数据库：
- sample_sentiment_dataset.py 的分层采样用鸭子类型的 SimpleNamespace 充当 NewsItem 行，
  DB 查询函数用 monkeypatch 替换。
- annotate_sentiment_dataset.py 的 LLM / 规则分类器全部用轻量 fake 对象注入
  （provider_factory / rule_classifier 都是显式传参，不需要 monkeypatch 真实 session）。
- review_sentiment_annotations.py 的终端交互用注入的 input_fn（列表弹出）驱动，不读真实 stdin。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from scripts.annotate_sentiment_dataset import (
    AnnotationStats,
    annotate_candidates,
    annotate_with_llm,
    annotate_with_rule,
)
from scripts.review_sentiment_annotations import (
    ReviewQuit,
    annotation_to_gold_sample,
    apply_review_decision,
    merge_gold_samples,
    run_review_session,
)
from scripts.sample_sentiment_dataset import (
    _bucket_key,
    _row_to_candidate,
    build_sentiment_dataset_candidates,
    stratified_sample,
)
from scripts.sentiment_dataset_lib import SentimentAnnotation, SentimentCandidate, read_jsonl, write_jsonl

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_dataset import default_gold_dataset_path, load_gold_samples

BASE_TIME = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


def _row(
    news_id: int,
    *,
    market: str = "us",
    sentiment_label: str | None = "positive",
    summary: str | None = None,
    published_at: datetime | None = None,
    title: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=news_id,
        title=title or f"title-{news_id}",
        summary=summary,
        market=market,
        sentiment_label=sentiment_label,
        published_at=published_at or (BASE_TIME + timedelta(minutes=news_id)),
        effective_at=BASE_TIME + timedelta(minutes=news_id),
    )


# ---------------------------------------------------------------------------
# sample_sentiment_dataset.py
# ---------------------------------------------------------------------------


def test_stratified_sample_prefers_rows_with_body_then_summary_within_bucket() -> None:
    no_content = _row(1, summary=None)
    with_body = _row(2, summary=None)
    with_summary_only = _row(3, summary="has summary")
    body_map = {2: "full article body"}

    selected = stratified_sample([no_content, with_body, with_summary_only], body_map, limit=2)

    assert [row.id for row in selected] == [2, 3]


def test_stratified_sample_balances_across_buckets_by_round_robin() -> None:
    negative_rows = [_row(20, market="us", sentiment_label="negative"), _row(21, market="us", sentiment_label="negative")]
    positive_rows = [
        _row(10, market="us", sentiment_label="positive"),
        _row(11, market="us", sentiment_label="positive"),
        _row(12, market="us", sentiment_label="positive"),
    ]

    selected = stratified_sample(negative_rows + positive_rows, {}, limit=4)

    assert len(selected) == 4
    counts = Counter(_bucket_key(row) for row in selected)
    assert counts[("us", "negative")] == 2
    assert counts[("us", "positive")] == 2


def test_stratified_sample_handles_empty_rows_and_non_positive_limit() -> None:
    assert stratified_sample([], {}, limit=10) == []
    assert stratified_sample([_row(1)], {}, limit=0) == []


def test_stratified_sample_returns_all_rows_when_limit_exceeds_pool() -> None:
    rows = [_row(1), _row(2, market="cn-a", sentiment_label=None)]
    selected = stratified_sample(rows, {}, limit=100)
    assert {row.id for row in selected} == {1, 2}


def test_bucket_key_falls_back_to_unlabeled_when_sentiment_label_missing() -> None:
    row = _row(1, sentiment_label=None)
    assert _bucket_key(row) == ("us", "unlabeled")


def test_row_to_candidate_maps_fields_and_uses_iso_published_at() -> None:
    row = _row(5, market="hk", sentiment_label="neutral", summary="s")
    candidate = _row_to_candidate(row, "body text")

    assert candidate.news_id == 5
    assert candidate.title == "title-5"
    assert candidate.summary == "s"
    assert candidate.body == "body text"
    assert candidate.market == "hk"
    assert candidate.existing_sentiment_label == "neutral"
    assert candidate.published_at == row.published_at.isoformat()


def test_build_sentiment_dataset_candidates_returns_empty_when_pool_is_empty(monkeypatch) -> None:
    import scripts.sample_sentiment_dataset as sample_module

    monkeypatch.setattr(sample_module, "_query_candidate_news_items", lambda session, pool_limit: [])

    def _fail_if_called(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("body excerpt map should not be queried for an empty pool")

    monkeypatch.setattr(sample_module, "_load_body_excerpt_map", _fail_if_called)

    result = build_sentiment_dataset_candidates(session=object(), limit=300)

    assert result == []


def test_build_sentiment_dataset_candidates_wires_query_and_body_map(monkeypatch) -> None:
    import scripts.sample_sentiment_dataset as sample_module

    rows = [_row(1, market="us", sentiment_label="positive"), _row(2, market="cn-a", sentiment_label="negative")]
    monkeypatch.setattr(sample_module, "_query_candidate_news_items", lambda session, pool_limit: rows)
    monkeypatch.setattr(
        sample_module,
        "_load_body_excerpt_map",
        lambda session, rows, *, excerpt_chars: {1: "body-1"},
    )

    candidates = build_sentiment_dataset_candidates(session=object(), limit=10)

    assert {c.news_id for c in candidates} == {1, 2}
    by_id = {c.news_id: c for c in candidates}
    assert by_id[1].body == "body-1"
    assert by_id[2].body is None


# ---------------------------------------------------------------------------
# annotate_sentiment_dataset.py
# ---------------------------------------------------------------------------


def _candidate(news_id: int = 1, *, title: str = "Nvidia beats estimates") -> SentimentCandidate:
    return SentimentCandidate(
        news_id=news_id,
        title=title,
        summary="summary text",
        body="body text",
        market="us",
        published_at="2026-08-01T00:00:00+00:00",
        existing_sentiment_label="positive",
    )


class _FakeProvider:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@dataclass
class _FakeRuleResult:
    sentiment_label: str
    sentiment_score: float


class _FakeRuleClassifier:
    def __init__(self, result: _FakeRuleResult | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def classify(self, *, title, summary, body, allow_llm):
        self.calls.append({"title": title, "summary": summary, "body": body, "allow_llm": allow_llm})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_annotate_with_llm_parses_valid_json_payload() -> None:
    provider = _FakeProvider('{"sentiment_label": "positive", "sentiment_score": 0.7, "reason": "业绩超预期"}')
    annotation = annotate_with_llm(_candidate(), provider)

    assert annotation.predicted_label == "positive"
    assert annotation.predicted_score == 0.7
    assert annotation.reason == "业绩超预期"
    assert annotation.annotator == "llm"
    assert annotation.status == "pending"
    assert "sentiment_label" in provider.calls[0]["system_prompt"]


def test_annotate_with_llm_parses_fenced_json_payload() -> None:
    fenced = '```json\n{"sentiment_label": "negative", "sentiment_score": -0.4, "reason": "营收下滑"}\n```'
    provider = _FakeProvider(fenced)
    annotation = annotate_with_llm(_candidate(), provider)

    assert annotation.predicted_label == "negative"
    assert annotation.predicted_score == -0.4


def test_annotate_with_llm_raises_on_invalid_payload() -> None:
    provider = _FakeProvider("not json at all")
    with pytest.raises(Exception):
        annotate_with_llm(_candidate(), provider)


def test_annotate_with_rule_uses_classifier_and_forces_offline() -> None:
    classifier = _FakeRuleClassifier(_FakeRuleResult(sentiment_label="negative", sentiment_score=-0.6))
    annotation = annotate_with_rule(_candidate(), classifier)

    assert annotation.predicted_label == "negative"
    assert annotation.predicted_score == -0.6
    assert annotation.annotator == "rule"
    assert classifier.calls[0]["allow_llm"] is False


def test_annotate_candidates_uses_llm_when_config_active() -> None:
    provider = _FakeProvider('{"sentiment_label": "positive", "sentiment_score": 0.5, "reason": "ok"}')
    classifier = _FakeRuleClassifier(_FakeRuleResult("neutral", 0.0))

    annotations, stats = annotate_candidates(
        [_candidate(1), _candidate(2)],
        active_config=SimpleNamespace(model_name="fake-model"),
        rule_classifier=classifier,
        provider_factory=lambda config: provider,
    )

    assert len(annotations) == 2
    assert all(item.annotator == "llm" for item in annotations)
    assert stats == AnnotationStats(llm_success=2, llm_failed=0, rule_used=0, skipped=0)
    assert classifier.calls == []  # 规则分类器全程没被调用


def test_annotate_candidates_falls_back_to_rule_when_llm_fails_for_one_sample() -> None:
    calls = {"n": 0}

    class _FlakyProvider:
        def generate_text(self, *, system_prompt, user_prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"sentiment_label": "positive", "sentiment_score": 0.3, "reason": "ok"}'
            raise RuntimeError("llm provider timed out")

    classifier = _FakeRuleClassifier(_FakeRuleResult("neutral", 0.0))

    annotations, stats = annotate_candidates(
        [_candidate(1), _candidate(2)],
        active_config=SimpleNamespace(model_name="fake-model"),
        rule_classifier=classifier,
        provider_factory=lambda config: _FlakyProvider(),
    )

    assert len(annotations) == 2
    assert annotations[0].annotator == "llm"
    assert annotations[1].annotator == "rule"
    assert stats == AnnotationStats(llm_success=1, llm_failed=1, rule_used=1, skipped=0)


def test_annotate_candidates_uses_rule_for_all_when_no_active_config() -> None:
    classifier = _FakeRuleClassifier(_FakeRuleResult("neutral", 0.05))
    provider_factory_calls: list[object] = []

    annotations, stats = annotate_candidates(
        [_candidate(1), _candidate(2)],
        active_config=None,
        rule_classifier=classifier,
        provider_factory=lambda config: provider_factory_calls.append(config),
    )

    assert len(annotations) == 2
    assert all(item.annotator == "rule" for item in annotations)
    assert stats == AnnotationStats(llm_success=0, llm_failed=0, rule_used=2, skipped=0)
    assert provider_factory_calls == []  # active_config 为 None 时不构造 provider


def test_annotate_candidates_skips_sample_when_rule_fallback_also_fails() -> None:
    classifier = _FakeRuleClassifier(RuntimeError("classifier exploded"))

    annotations, stats = annotate_candidates(
        [_candidate(1)],
        active_config=None,
        rule_classifier=classifier,
    )

    assert annotations == []
    assert stats.skipped == 1


# ---------------------------------------------------------------------------
# review_sentiment_annotations.py
# ---------------------------------------------------------------------------


def _annotation(
    news_id: int = 1,
    *,
    predicted_label: str = "positive",
    predicted_score: float = 0.6,
    annotator: str = "llm",
) -> SentimentAnnotation:
    return SentimentAnnotation(
        news_id=news_id,
        title=f"title-{news_id}",
        summary="summary",
        body="body",
        market="us",
        published_at=None,
        existing_sentiment_label=None,
        predicted_label=predicted_label,
        predicted_score=predicted_score,
        reason="reason text",
        annotator=annotator,
        status="pending",
    )


def test_apply_review_decision_accept_keeps_predicted_label() -> None:
    result = apply_review_decision(_annotation(predicted_label="negative"), "y")
    assert result.status == "accepted"
    assert result.reviewed_label == "negative"


def test_apply_review_decision_empty_input_accepts_like_y() -> None:
    result = apply_review_decision(_annotation(predicted_label="neutral"), "")
    assert result.status == "accepted"
    assert result.reviewed_label == "neutral"


@pytest.mark.parametrize("key,expected", [("p", "positive"), ("n", "negative"), ("u", "neutral")])
def test_apply_review_decision_overrides_label(key: str, expected: str) -> None:
    result = apply_review_decision(_annotation(predicted_label="positive"), key)
    assert result.status == "accepted"
    assert result.reviewed_label == expected


def test_apply_review_decision_skip() -> None:
    result = apply_review_decision(_annotation(), "s")
    assert result.status == "skipped"
    assert result.reviewed_label is None


def test_apply_review_decision_quit_raises() -> None:
    with pytest.raises(ReviewQuit):
        apply_review_decision(_annotation(), "q")


def test_apply_review_decision_rejects_unknown_input() -> None:
    with pytest.raises(ValueError):
        apply_review_decision(_annotation(), "z")


def test_annotation_to_gold_sample_maps_fields_and_derives_importance() -> None:
    annotation = _annotation(news_id=42, predicted_label="positive", predicted_score=0.6)
    accepted = apply_review_decision(annotation, "y")

    gold = annotation_to_gold_sample(accepted)

    assert gold.sample_id == "gold-42"
    assert gold.text == annotation.title
    assert gold.title == annotation.title
    assert gold.summary == annotation.summary
    assert gold.body == annotation.body
    assert gold.market == annotation.market
    assert gold.news_id == 42
    assert gold.sentiment_label == "positive"
    assert gold.importance == 0.6


def test_annotation_to_gold_sample_uses_reviewed_label_override() -> None:
    annotation = _annotation(news_id=1, predicted_label="positive", predicted_score=0.6)
    overridden = apply_review_decision(annotation, "n")

    gold = annotation_to_gold_sample(overridden)

    assert gold.sentiment_label == "negative"


def test_annotation_to_gold_sample_importance_has_floor_for_low_confidence_scores() -> None:
    annotation = _annotation(news_id=1, predicted_label="neutral", predicted_score=0.02)
    accepted = apply_review_decision(annotation, "y")

    gold = annotation_to_gold_sample(accepted)

    assert gold.importance == 0.3


def test_merge_gold_samples_overwrites_same_sample_id_and_dedups_by_news_id() -> None:
    existing = [SentimentGoldSample(sample_id="gold-1", text="old", sentiment_label="positive", news_id=1)]
    new_samples = [
        SentimentGoldSample(sample_id="gold-1", text="updated", sentiment_label="negative", news_id=1),
        SentimentGoldSample(sample_id="dup-1", text="dup", sentiment_label="neutral", news_id=1),
        SentimentGoldSample(sample_id="gold-2", text="fresh", sentiment_label="neutral", news_id=2),
    ]

    merged = merge_gold_samples(existing, new_samples)

    assert {s.sample_id for s in merged} == {"gold-1", "gold-2"}
    assert next(s for s in merged if s.sample_id == "gold-1").text == "updated"


def test_merge_gold_samples_preserves_legacy_samples_without_news_id() -> None:
    existing = [SentimentGoldSample(sample_id="pos-en-01", text="legacy sample", sentiment_label="positive")]
    new_samples = [SentimentGoldSample(sample_id="gold-1", text="new", sentiment_label="negative", news_id=1)]

    merged = merge_gold_samples(existing, new_samples)

    assert {s.sample_id for s in merged} == {"pos-en-01", "gold-1"}


def test_run_review_session_collects_accepted_and_skipped_decisions() -> None:
    annotations = [_annotation(1), _annotation(2)]
    inputs = iter(["s", "y"])

    reviewed = run_review_session(annotations, input_fn=lambda _prompt: next(inputs), print_fn=lambda _msg: None)

    assert [item.status for item in reviewed] == ["skipped", "accepted"]


def test_run_review_session_stops_early_on_quit() -> None:
    annotations = [_annotation(1), _annotation(2), _annotation(3)]
    inputs = iter(["y", "q"])

    reviewed = run_review_session(annotations, input_fn=lambda _prompt: next(inputs), print_fn=lambda _msg: None)

    assert [item.news_id for item in reviewed] == [1]


def test_run_review_session_reprompts_on_invalid_input() -> None:
    annotations = [_annotation(1)]
    inputs = iter(["not-a-valid-choice", "y"])

    reviewed = run_review_session(annotations, input_fn=lambda _prompt: next(inputs), print_fn=lambda _msg: None)

    assert len(reviewed) == 1
    assert reviewed[0].status == "accepted"


# ---------------------------------------------------------------------------
# sentiment_dataset_lib.py + 向后兼容
# ---------------------------------------------------------------------------


def test_read_jsonl_returns_empty_list_for_missing_file(tmp_path) -> None:
    assert read_jsonl(tmp_path / "does-not-exist.jsonl", SentimentCandidate) == []


def test_write_jsonl_then_read_jsonl_roundtrip(tmp_path) -> None:
    path = tmp_path / "candidates.jsonl"
    candidates = [_candidate(1), _candidate(2, title="second")]

    write_jsonl(path, candidates)
    loaded = read_jsonl(path, SentimentCandidate)

    assert [c.news_id for c in loaded] == [1, 2]
    assert loaded[1].title == "second"


def test_legacy_builtin_gold_benchmark_still_loads_after_schema_extension() -> None:
    samples = load_gold_samples(default_gold_dataset_path())

    assert len(samples) == 20
    assert all(sample.title is None for sample in samples)  # legacy 手写样本没有 title，靠 effective_title 兜底
    assert all(sample.effective_title == sample.text for sample in samples)
