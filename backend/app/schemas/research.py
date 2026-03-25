from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import UTCDateTime

LabelSource = Literal["model_only", "human_reviewed", "human_corrected"]
NoiseType = Literal[
    "generic_tech",
    "lifestyle_or_entertainment",
    "duplicate_or_rewrite",
    "low_information",
    "off_topic",
    "other",
]


class MarketRelevanceOrigin(BaseModel):
    news_id: int | None = None
    source_name: str
    canonical_url: str
    published_at: UTCDateTime | None = None


class MarketRelevanceContent(BaseModel):
    title: str
    summary: str | None = None
    body_excerpt: str | None = None


class MarketRelevanceLabel(BaseModel):
    market_relevant: bool
    noise_type: NoiseType | None = None

    @model_validator(mode="after")
    def validate_noise_type(self) -> "MarketRelevanceLabel":
        if self.market_relevant and self.noise_type is not None:
            raise ValueError("noise_type must be null when market_relevant is true")
        if not self.market_relevant and self.noise_type is None:
            raise ValueError("noise_type is required when market_relevant is false")
        return self


class MarketRelevanceAnnotation(BaseModel):
    label_source: LabelSource
    model_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    review_notes: str = ""


class MarketRelevanceSample(BaseModel):
    sample_id: str
    source_type: Literal["historical", "realtime"]
    origin: MarketRelevanceOrigin
    content: MarketRelevanceContent
    labels: MarketRelevanceLabel
    annotation: MarketRelevanceAnnotation
    predicted_market_relevant: bool | None = None


class EvaluationMetrics(BaseModel):
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    noise_rejection_rate: float = Field(ge=0.0, le=1.0)


class ExperimentDecision(BaseModel):
    experiment_id: str
    decision: Literal["baseline", "keep", "reject"]
    reason: str
    metrics_before: EvaluationMetrics
    metrics_after: EvaluationMetrics

    @model_validator(mode="after")
    def validate_reason(self) -> "ExperimentDecision":
        if not self.reason.strip():
            raise ValueError("reason is required")
        return self
