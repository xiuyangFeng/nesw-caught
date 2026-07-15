from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# 情绪评测只涵盖三分类，和 news_signal_classifier 的输出标签保持一致。
SentimentLabel = Literal["positive", "negative", "neutral"]
SENTIMENT_LABELS: tuple[SentimentLabel, ...] = ("positive", "negative", "neutral")


class SentimentGoldSample(BaseModel):
    """情绪/利好利空金标样本：一段文本 + 人工标注标签，importance 可选。"""

    sample_id: str
    text: str
    sentiment_label: SentimentLabel
    # importance 为可选人工标注（0~1 的重要度打分），缺省时不参与评测。
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    # 模型预测标签，评测前由分类器填充；金标文件里通常为空。
    predicted_sentiment: SentimentLabel | None = None

    @model_validator(mode="after")
    def validate_text(self) -> SentimentGoldSample:
        if not self.text.strip():
            raise ValueError("text is required")
        return self


class SentimentLabelMetrics(BaseModel):
    label: SentimentLabel
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    support: int = Field(ge=0)


class SentimentEvaluationMetrics(BaseModel):
    accuracy: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    per_label: list[SentimentLabelMetrics]
    # confusion_matrix[actual][predicted] = 计数
    confusion_matrix: dict[str, dict[str, int]]


class SentimentModelRun(BaseModel):
    model_name: str
    metrics: SentimentEvaluationMetrics


class SentimentLabelDelta(BaseModel):
    label: SentimentLabel
    f1_before: float = Field(ge=0.0, le=1.0)
    f1_after: float = Field(ge=0.0, le=1.0)
    f1_delta: float


class SentimentABComparison(BaseModel):
    model_a: SentimentModelRun
    model_b: SentimentModelRun
    accuracy_delta: float
    macro_f1_delta: float
    label_deltas: list[SentimentLabelDelta]
    winner: Literal["model_a", "model_b", "tie"]
    reason: str

    @model_validator(mode="after")
    def validate_reason(self) -> SentimentABComparison:
        if not self.reason.strip():
            raise ValueError("reason is required")
        return self


class SentimentEvalResponse(BaseModel):
    """GET /eval/sentiment 的返回体。available=False 表示金标缺失时的降级。"""

    available: bool
    dataset_path: str
    sample_count: int
    primary: SentimentModelRun | None = None
    comparison: SentimentABComparison | None = None
    note: str | None = None
