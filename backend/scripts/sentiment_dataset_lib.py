"""情绪金标数据集工具链的共享数据结构与 JSONL 读写辅助。

被 sample_sentiment_dataset.py / annotate_sentiment_dataset.py /
review_sentiment_annotations.py 三个脚本共用，镜像 market_relevance 链路
（app/services/news_relevance_dataset.py）的风格，但因为 app/schemas 在本次
重构中由其他工作块并行修改，这里的中间态模型只作为脚本间交换格式，不落进
app/schemas。

三段流水线：
1. sample_sentiment_dataset.py  -> SentimentCandidate（DB 分层采样候选）
2. annotate_sentiment_dataset.py -> SentimentAnnotation（预标注，待复核）
3. review_sentiment_annotations.py -> app.schemas.sentiment_eval.SentimentGoldSample（人工复核后落金标）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

SentimentLabel = Literal["positive", "negative", "neutral"]
SENTIMENT_LABELS: tuple[SentimentLabel, ...] = ("positive", "negative", "neutral")

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class SentimentCandidate(BaseModel):
    """sample_sentiment_dataset.py 产出的候选样本（预标注前）。"""

    news_id: int
    title: str
    summary: str | None = None
    body: str | None = None
    market: str
    published_at: str | None = None
    # 采样时 NewsItem 上已有的情绪标签（分层维度），信息性字段，不参与后续判定。
    existing_sentiment_label: str | None = None

    @model_validator(mode="after")
    def _validate_title(self) -> SentimentCandidate:
        if not self.title.strip():
            raise ValueError("title is required")
        return self


class SentimentAnnotation(SentimentCandidate):
    """annotate_sentiment_dataset.py 产出的预标注样本（待人工复核）。"""

    predicted_label: SentimentLabel
    predicted_score: float = Field(ge=-1.0, le=1.0)
    reason: str
    annotator: Literal["llm", "rule"]
    status: Literal["pending", "accepted", "skipped"] = "pending"
    reviewed_label: SentimentLabel | None = None

    @model_validator(mode="after")
    def _validate_reason(self) -> SentimentAnnotation:
        if not self.reason.strip():
            raise ValueError("reason is required")
        return self


def read_jsonl(path: str | Path, model: type[_ModelT]) -> list[_ModelT]:
    """按行读取 JSONL，文件不存在时返回空列表（供上层优雅提示退出）。"""
    input_path = Path(path)
    if not input_path.exists():
        return []
    items: list[_ModelT] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        items.append(model.model_validate(json.loads(stripped)))
    return items


def write_jsonl(path: str | Path, items: list[BaseModel]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.model_dump_json())
            handle.write("\n")
