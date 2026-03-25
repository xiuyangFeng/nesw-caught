from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.schemas.research import MarketRelevanceAnnotation, MarketRelevanceLabel, MarketRelevanceSample
from app.services.news_relevance_annotation import (
    MarketRelevanceAnnotationError,
    MarketRelevanceAnnotationService,
    annotate_market_relevance_file,
)


def _sample_payload(sample_id: str = "sample-1") -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source_type": "historical",
        "origin": {
            "news_id": 42,
            "source_name": "Reuters",
            "canonical_url": f"https://example.com/{sample_id}",
            "published_at": "2026-03-25T00:00:00Z",
        },
        "content": {
            "title": "Central bank signals policy pause",
            "summary": "Markets react to the latest policy guidance.",
            "body_excerpt": "Officials suggested rates may stay unchanged for now.",
        },
        "labels": {
            "market_relevant": True,
            "noise_type": None,
        },
        "annotation": {
            "label_source": "model_only",
            "model_name": "deepseek-chat",
            "confidence": 0.0,
            "review_notes": "",
        },
    }


def test_annotation_service_parses_market_relevance_schema(monkeypatch) -> None:
    sample = MarketRelevanceSample.model_validate(_sample_payload())
    fake_config = SimpleNamespace(provider_name="openai_compatible", model_name="deepseek-chat")

    captured = {}

    def fake_generate_text(self, *, system_prompt: str, user_prompt: str) -> str:  # type: ignore[no-untyped-def]
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return json.dumps(
            {
                "market_relevant": False,
                "noise_type": "off_topic",
                "confidence": 0.18,
                "reason": "The story is about policy messaging, not a listed-equity read-through.",
            }
        )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.LLMProviderConfigRepository.get_active",
        lambda self: fake_config,
    )
    monkeypatch.setattr(
        "app.services.news_relevance_annotation.build_provider",
        lambda config: SimpleNamespace(generate_text=fake_generate_text.__get__(SimpleNamespace(), object)),
    )

    service = MarketRelevanceAnnotationService(session=object())
    annotated = service.annotate_sample(sample)

    assert "market_relevant" in captured["system_prompt"]
    assert "noise_type" in captured["system_prompt"]
    assert "confidence" in captured["system_prompt"]
    assert "reason" in captured["system_prompt"]
    assert "Central bank signals policy pause" in captured["user_prompt"]
    assert annotated.labels == MarketRelevanceLabel(market_relevant=False, noise_type="off_topic")
    assert annotated.annotation == MarketRelevanceAnnotation(
        label_source="model_only",
        model_name="deepseek-chat",
        confidence=0.18,
        review_notes="The story is about policy messaging, not a listed-equity read-through.",
    )


def test_annotation_service_requires_llm_provider_config() -> None:
    service = MarketRelevanceAnnotationService(session=object())
    service.config_repository.get_active = lambda: None  # type: ignore[method-assign]

    with pytest.raises(MarketRelevanceAnnotationError, match="llm provider is not configured"):
        service.annotate_sample(MarketRelevanceSample.model_validate(_sample_payload()))


def test_annotation_service_rejects_placeholder_provider_config(monkeypatch) -> None:
    sample = MarketRelevanceSample.model_validate(_sample_payload())
    fake_config = SimpleNamespace(
        provider_name="openai_compatible",
        model_name="deepseek-chat",
        base_url="https://example-llm.test/v1",
        api_key="sk-test-placeholder",
    )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.LLMProviderConfigRepository.get_active",
        lambda self: fake_config,
    )

    service = MarketRelevanceAnnotationService(session=object())

    with pytest.raises(MarketRelevanceAnnotationError, match="placeholder"):
        service.annotate_sample(sample)


def test_annotation_service_allows_non_placeholder_hostnames_that_start_with_example(monkeypatch) -> None:
    sample = MarketRelevanceSample.model_validate(_sample_payload())
    fake_config = SimpleNamespace(
        provider_name="openai_compatible",
        model_name="deepseek-chat",
        base_url="https://example-llm.company.com/v1",
        api_key="sk-live-realistic",
    )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.LLMProviderConfigRepository.get_active",
        lambda self: fake_config,
    )
    monkeypatch.setattr(
        "app.services.news_relevance_annotation.build_provider",
        lambda config: SimpleNamespace(
            generate_text=lambda **kwargs: json.dumps(
                {
                    "market_relevant": True,
                    "noise_type": None,
                    "confidence": 0.88,
                    "reason": "Business update has clear investor relevance.",
                }
            )
        ),
    )

    annotated = MarketRelevanceAnnotationService(session=object()).annotate_sample(sample)

    assert annotated.annotation.confidence == 0.88


def test_annotate_market_relevance_file_writes_annotated_jsonl(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "annotated.jsonl"
    input_path.write_text(json.dumps(_sample_payload()) + "\n", encoding="utf-8")

    def fake_annotate_sample(self, sample):  # type: ignore[no-untyped-def]
        return sample.model_copy(
            update={
                "labels": MarketRelevanceLabel(market_relevant=False, noise_type="low_information"),
                "annotation": MarketRelevanceAnnotation(
                    label_source="model_only",
                    model_name="deepseek-chat",
                    confidence=0.64,
                    review_notes="Short, generic report with no market-specific catalyst.",
                ),
            }
        )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.MarketRelevanceAnnotationService.annotate_sample",
        fake_annotate_sample,
    )

    annotated_samples = annotate_market_relevance_file(input_path, output_path, session=object())

    assert len(annotated_samples) == 1
    assert annotated_samples[0].labels == MarketRelevanceLabel(market_relevant=False, noise_type="low_information")
    output_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(output_lines) == 1
    persisted = json.loads(output_lines[0])
    assert persisted["labels"]["market_relevant"] is False
    assert persisted["labels"]["noise_type"] == "low_information"
    assert persisted["annotation"]["confidence"] == 0.64


def test_annotate_market_relevance_file_can_resume_from_existing_output(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "annotated.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(_sample_payload("sample-1")),
                json.dumps(_sample_payload("sample-2")),
                json.dumps(_sample_payload("sample-3")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    completed = _sample_payload("sample-1")
    completed["annotation"] = {
        "label_source": "model_only",
        "model_name": "deepseek-chat",
        "confidence": 0.77,
        "review_notes": "annotated sample-1",
    }
    output_path.write_text(json.dumps(completed) + "\n", encoding="utf-8")

    seen: list[str] = []

    def fake_annotate_sample(self, sample):  # type: ignore[no-untyped-def]
        seen.append(sample.sample_id)
        return sample.model_copy(
            update={
                "annotation": MarketRelevanceAnnotation(
                    label_source="model_only",
                    model_name="deepseek-chat",
                    confidence=0.77,
                    review_notes=f"annotated {sample.sample_id}",
                )
            }
        )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.MarketRelevanceAnnotationService.annotate_sample",
        fake_annotate_sample,
    )

    annotated_samples = annotate_market_relevance_file(
        input_path,
        output_path,
        session=object(),
        resume=True,
    )

    assert [sample.sample_id for sample in annotated_samples] == ["sample-1", "sample-2", "sample-3"]
    assert seen == ["sample-2", "sample-3"]
    output_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["sample_id"] for line in output_lines] == ["sample-1", "sample-2", "sample-3"]


def test_annotate_market_relevance_file_resume_reannotates_placeholder_rows(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "annotated.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(_sample_payload("sample-1")),
                json.dumps(_sample_payload("sample-2")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_path.write_text(json.dumps(_sample_payload("sample-1")) + "\n", encoding="utf-8")

    seen: list[str] = []

    def fake_annotate_sample(self, sample):  # type: ignore[no-untyped-def]
        seen.append(sample.sample_id)
        return sample.model_copy(
            update={
                "annotation": MarketRelevanceAnnotation(
                    label_source="model_only",
                    model_name="deepseek-chat",
                    confidence=0.81,
                    review_notes=f"annotated {sample.sample_id}",
                )
            }
        )

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.MarketRelevanceAnnotationService.annotate_sample",
        fake_annotate_sample,
    )

    annotated_samples = annotate_market_relevance_file(
        input_path,
        output_path,
        session=object(),
        resume=True,
    )

    assert [sample.sample_id for sample in annotated_samples] == ["sample-1", "sample-2"]
    assert seen == ["sample-1", "sample-2"]


def test_annotate_market_relevance_file_flushes_each_batch(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "annotated.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(_sample_payload("sample-1")),
                json.dumps(_sample_payload("sample-2")),
                json.dumps(_sample_payload("sample-3")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_annotate_sample(self, sample):  # type: ignore[no-untyped-def]
        return sample.model_copy(
            update={
                "annotation": MarketRelevanceAnnotation(
                    label_source="model_only",
                    model_name="deepseek-chat",
                    confidence=0.8,
                    review_notes=f"annotated {sample.sample_id}",
                )
            }
        )

    def fake_save_samples(path, samples):  # type: ignore[no-untyped-def]
        calls.append([sample.sample_id for sample in samples])

    monkeypatch.setattr(
        "app.services.news_relevance_annotation.MarketRelevanceAnnotationService.annotate_sample",
        fake_annotate_sample,
    )
    monkeypatch.setattr("app.services.news_relevance_annotation.save_samples", fake_save_samples)

    annotate_market_relevance_file(
        input_path,
        output_path,
        session=object(),
        batch_size=2,
    )

    assert calls == [["sample-1", "sample-2"], ["sample-1", "sample-2", "sample-3"]]


@pytest.mark.parametrize("batch_size", [0, -1])
def test_annotate_market_relevance_file_rejects_non_positive_batch_size(tmp_path, batch_size) -> None:
    input_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "annotated.jsonl"
    input_path.write_text(json.dumps(_sample_payload("sample-1")) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="batch_size"):
        annotate_market_relevance_file(
            input_path,
            output_path,
            session=object(),
            batch_size=batch_size,
        )
