"""SentimentEvalRun 落库/读回的序列化与历史/回归计算逻辑。

从 app/api/routes/eval.py 拆出来是为了能脱离 FastAPI/DB fixture 单独单测——
路由本身只做「取样本 -> 跑评测 -> 调这里的纯函数 -> 落库/拼响应」的编排。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.models.sentiment_eval_run import SentimentEvalRun
from app.schemas.sentiment_eval import (
    SentimentABComparison,
    SentimentEvalHistoryEntry,
    SentimentEvalHistoryPoint,
    SentimentEvalRegression,
    SentimentEvaluationMetrics,
    SentimentLabelMetrics,
    SentimentModelRun,
)
from app.services.news_sentiment_experiment_runner import compare_sentiment_runs

# macro_f1 下降超过这个幅度才判定为回归（设计文档「SentimentEvalResponse 扩展」节）。
REGRESSION_MACRO_F1_DROP_THRESHOLD = 0.02


def compute_dataset_hash(dataset_path: str | Path) -> str:
    """金标文件内容 sha256 前 16 位，用于识别"同一份数据集"的历史 batch。"""
    content = Path(dataset_path).read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def serialize_run_for_storage(run: SentimentModelRun) -> dict[str, object]:
    """把一个 SentimentModelRun 拆成落库所需的 JSON 字段。"""
    return {
        "model_name": run.model_name,
        "accuracy": run.metrics.accuracy,
        "macro_f1": run.metrics.macro_f1,
        "importance_weighted_accuracy": run.metrics.importance_weighted_accuracy,
        "per_label_json": json.dumps(
            [item.model_dump() for item in run.metrics.per_label], ensure_ascii=False
        ),
        "confusion_json": json.dumps(run.metrics.confusion_matrix, ensure_ascii=False),
    }


def deserialize_run(row: SentimentEvalRun) -> SentimentModelRun:
    """把落库的一行还原成 SentimentModelRun，供 GET 只读回放使用。"""
    per_label_raw = json.loads(row.per_label_json)
    confusion_matrix = json.loads(row.confusion_json)
    metrics = SentimentEvaluationMetrics(
        accuracy=row.accuracy,
        macro_f1=row.macro_f1,
        sample_count=row.sample_count,
        per_label=[SentimentLabelMetrics(**item) for item in per_label_raw],
        confusion_matrix=confusion_matrix,
        importance_weighted_accuracy=row.importance_weighted_accuracy,
    )
    return SentimentModelRun(model_name=row.model_name, metrics=metrics)


def pick_comparison(runs: list[SentimentModelRun]) -> SentimentABComparison | None:
    """comparison 固定 model_a=rule-baseline，model_b=llm:*（有）或 rule-sensitive（无）。"""
    by_name = {run.model_name: run for run in runs}
    model_a = by_name.get("rule-baseline")
    if model_a is None:
        return None

    model_b = next((run for run in runs if run.model_name.startswith("llm:")), None)
    if model_b is None:
        model_b = next(
            (run for run in runs if run.model_name.startswith("rule-sensitive")), None
        )
    if model_b is None:
        return None

    return compare_sentiment_runs(model_a, model_b)


def build_history(batches: list[list[SentimentEvalRun]]) -> list[SentimentEvalHistoryPoint]:
    """把最近若干个 batch（每个 batch 是一组同 batch_id 的行）摘要成历史走势点位。"""
    points: list[SentimentEvalHistoryPoint] = []
    for batch in batches:
        if not batch:
            continue
        head = batch[0]
        points.append(
            SentimentEvalHistoryPoint(
                batch_id=head.batch_id,
                evaluated_at=head.created_at,
                dataset_hash=head.dataset_hash,
                sample_count=head.sample_count,
                entries=[
                    SentimentEvalHistoryEntry(
                        model_name=row.model_name,
                        accuracy=row.accuracy,
                        macro_f1=row.macro_f1,
                    )
                    for row in batch
                ],
            )
        )
    return points


def compute_regression(
    *,
    previous_batch: list[SentimentEvalRun],
    current_runs: list[SentimentModelRun],
) -> tuple[SentimentEvalRegression | None, list[SentimentEvalRegression]]:
    """当前 runs 与上一个同 dataset_hash batch 的同名模型逐个比 macro_f1。

    返回 (跌幅最大者, 其余同样判定为回归的模型列表)——前者进 response.regression，
    后者由调用方拼进 note（"多个模型有回归时取跌幅最大者，其余写进 note"）。
    没有可比较的历史 batch，或没有同名模型时返回 (None, [])。
    """
    if not previous_batch:
        return None, []

    previous_by_name = {row.model_name: row for row in previous_batch}
    deltas: list[SentimentEvalRegression] = []
    for run in current_runs:
        previous_row = previous_by_name.get(run.model_name)
        if previous_row is None:
            continue
        delta = round(run.metrics.macro_f1 - previous_row.macro_f1, 4)
        deltas.append(
            SentimentEvalRegression(
                model_name=run.model_name,
                previous_macro_f1=previous_row.macro_f1,
                current_macro_f1=run.metrics.macro_f1,
                delta=delta,
                regressed=delta < -REGRESSION_MACRO_F1_DROP_THRESHOLD,
            )
        )

    if not deltas:
        return None, []

    worst = min(deltas, key=lambda item: item.delta)
    other_regressed = [
        item for item in deltas if item.regressed and item.model_name != worst.model_name
    ]
    return worst, other_regressed


def evaluated_at_of(batch: list[SentimentEvalRun]) -> datetime | None:
    return batch[0].created_at if batch else None
