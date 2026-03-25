from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.schemas.research import MarketRelevanceAnnotation, MarketRelevanceLabel, MarketRelevanceSample
from app.services.llm_providers import LLMProviderError, build_provider
from app.services.news_relevance_dataset import save_samples


class MarketRelevanceAnnotationError(RuntimeError):
    pass


NoiseType = Literal[
    "generic_tech",
    "lifestyle_or_entertainment",
    "duplicate_or_rewrite",
    "low_information",
    "off_topic",
    "other",
]


class MarketRelevancePrediction(BaseModel):
    market_relevant: bool
    noise_type: NoiseType | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    @model_validator(mode="after")
    def validate_noise_type(self) -> "MarketRelevancePrediction":
        if self.market_relevant and self.noise_type is not None:
            raise ValueError("noise_type must be null when market_relevant is true")
        if not self.market_relevant and self.noise_type is None:
            raise ValueError("noise_type is required when market_relevant is false")
        if not self.reason.strip():
            raise ValueError("reason is required")
        return self


class MarketRelevanceAnnotationService:
    def __init__(self, session) -> None:
        self.session = session
        self.config_repository = LLMProviderConfigRepository(session)

    def annotate_sample(self, sample: MarketRelevanceSample) -> MarketRelevanceSample:
        config = self.config_repository.get_active()
        if config is None:
            raise MarketRelevanceAnnotationError("llm provider is not configured")

        provider = build_provider(config)
        system_prompt, user_prompt = self._build_prompts(sample)

        try:
            content = provider.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)
        except LLMProviderError as exc:
            raise MarketRelevanceAnnotationError(str(exc)) from exc

        prediction = self._parse_prediction(content)
        return sample.model_copy(
            update={
                "labels": MarketRelevanceLabel(
                    market_relevant=prediction.market_relevant,
                    noise_type=prediction.noise_type,
                ),
                "annotation": MarketRelevanceAnnotation(
                    label_source="model_only",
                    model_name=config.model_name,
                    confidence=prediction.confidence,
                    review_notes=prediction.reason,
                ),
            }
        )

    def _build_prompts(self, sample: MarketRelevanceSample) -> tuple[str, str]:
        system_prompt = (
            "You label whether a news item is market relevant for listed equities. "
            "Return JSON only with keys: market_relevant, noise_type, confidence, reason. "
            "If market_relevant is true, noise_type must be null. "
            "If market_relevant is false, noise_type must be one of: "
            "generic_tech, lifestyle_or_entertainment, duplicate_or_rewrite, low_information, off_topic, other. "
            "confidence must be a number from 0 to 1. reason must be a short explanation."
        )
        user_prompt = "\n".join(
            [
                f"Sample ID: {sample.sample_id}",
                f"Source Type: {sample.source_type}",
                f"Source: {sample.origin.source_name}",
                f"Canonical URL: {sample.origin.canonical_url}",
                f"Published At: {sample.origin.published_at.isoformat() if sample.origin.published_at else ''}",
                f"Title: {sample.content.title}",
                f"Summary: {sample.content.summary or ''}",
                f"Body Excerpt: {sample.content.body_excerpt or ''}",
            ]
        )
        return system_prompt, user_prompt

    def _parse_prediction(self, content: str) -> MarketRelevancePrediction:
        payload = _extract_json_payload(content)
        try:
            return MarketRelevancePrediction.model_validate_json(payload)
        except Exception as exc:
            raise MarketRelevanceAnnotationError("llm provider returned invalid annotation payload") from exc


def annotate_market_relevance_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    session,
) -> list[MarketRelevanceSample]:
    samples = [_load_sample(line) for line in _read_jsonl_lines(input_path)]
    service = MarketRelevanceAnnotationService(session)
    annotated = [service.annotate_sample(sample) for sample in samples]
    save_samples(output_path, annotated)
    return annotated


def _read_jsonl_lines(path: str | Path) -> list[str]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    return [line for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_sample(raw_line: str) -> MarketRelevanceSample:
    return MarketRelevanceSample.model_validate(json.loads(raw_line))


def _extract_json_payload(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            stripped = "\n".join(lines[1:-1]).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped
