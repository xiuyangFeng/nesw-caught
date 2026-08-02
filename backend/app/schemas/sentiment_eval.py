from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# 情绪评测只涵盖三分类，和 news_signal_classifier 的输出标签保持一致。
SentimentLabel = Literal["positive", "negative", "neutral"]
SENTIMENT_LABELS: tuple[SentimentLabel, ...] = ("positive", "negative", "neutral")


class SentimentGoldSample(BaseModel):
    """情绪/利好利空金标样本：一段文本 + 人工标注标签，importance 可选。

    title/summary/body/market 为真实新闻采样的可选字段，与线上分类输入对齐；
    缺省时以 text 充当 title（legacy 手写样本行为）。
    """

    sample_id: str
    text: str
    sentiment_label: SentimentLabel
    # 与线上 classify(title, summary, body) 输入对齐的可选字段。
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    # 命中市场（如 us / cn-a / hk），影响中英词典路径。
    market: str | None = None
    # 采样来源 NewsItem id，便于追溯。
    news_id: int | None = None
    # importance 为可选人工标注（0~1 的重要度打分），参与加权准确率计算。
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    # 模型预测标签，评测前由分类器填充；金标文件里通常为空。
    predicted_sentiment: SentimentLabel | None = None

    @model_validator(mode="after")
    def validate_text(self) -> SentimentGoldSample:
        if not self.text.strip():
            raise ValueError("text is required")
        return self

    @property
    def effective_title(self) -> str:
        return self.title or self.text


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
    # 有 importance 标注的样本按权重的加权准确率（无标注样本权重 1.0）；
    # 数据集内所有样本都没有 importance 标注时为 None。
    importance_weighted_accuracy: float | None = None


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


class SentimentEvalHistoryEntry(BaseModel):
    """history[].entries[] 的单个模型摘要点位。"""

    model_name: str
    accuracy: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)


class SentimentEvalHistoryPoint(BaseModel):
    """一次 POST /sentiment/run 触发的 batch 摘要（GET 返回最近 20 个）。"""

    batch_id: str
    evaluated_at: datetime
    dataset_hash: str
    sample_count: int
    entries: list[SentimentEvalHistoryEntry]


class SentimentEvalRegression(BaseModel):
    """最新 batch 与上一个同 dataset_hash batch 的同名模型对比（跌幅最大者）。"""

    model_name: str
    previous_macro_f1: float = Field(ge=0.0, le=1.0)
    current_macro_f1: float = Field(ge=0.0, le=1.0)
    delta: float
    regressed: bool


class SentimentEvalResponse(BaseModel):
    """GET /eval/sentiment 的返回体。available=False 表示金标缺失时的降级。"""

    available: bool
    dataset_path: str
    sample_count: int
    primary: SentimentModelRun | None = None
    comparison: SentimentABComparison | None = None
    note: str | None = None
    # 最近一个 batch 的评测时间；库里尚无记录时为 None。
    evaluated_at: datetime | None = None
    # 本 batch 全部模型 run（rule/llm/hybrid），primary 始终指向 rule-baseline。
    runs: list[SentimentModelRun] = Field(default_factory=list)
    # 是否存在激活的 LLM provider 配置（与本 batch 运行时是否用了 LLM 无关，取当前状态）。
    llm_available: bool = False
    # 最近 20 个 batch 的 macro_f1 走势摘要。
    history: list[SentimentEvalHistoryPoint] = Field(default_factory=list)
    # 与上一个同 dataset_hash batch 的回归对比；无可比较历史时为 None。
    regression: SentimentEvalRegression | None = None
