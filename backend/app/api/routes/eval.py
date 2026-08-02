from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.sentiment_eval_run_repository import SentimentEvalRunRepository
from app.schemas.sentiment_eval import (
    SentimentABComparison,
    SentimentEvalResponse,
    SentimentGoldSample,
    SentimentModelRun,
)
from app.services.news_sentiment_dataset import (
    InvalidGoldSampleError,
    default_gold_dataset_path,
    load_gold_samples,
)
from app.services.news_sentiment_evaluator import (
    build_hybrid_sentiment_classifier,
    build_rule_sentiment_classifier,
)
from app.services.news_sentiment_experiment_runner import compare_sentiment_runs, run_sentiment_evaluation
from app.services.news_sentiment_llm_classifier import (
    SENTIMENT_EVAL_CACHE_SCOPE,
    NewsSentimentLLMClassifier,
)
from app.services.news_signal_classifier import NewsSignalClassifier
from app.services.sentiment_eval_persistence import (
    build_history,
    compute_dataset_hash,
    compute_regression,
    deserialize_run,
    evaluated_at_of,
    pick_comparison,
    serialize_run_for_storage,
)

router = APIRouter()

_REGRESSION_HISTORY_LIMIT = 20


def _resolve_dataset_path() -> str:
    settings = get_settings()
    return settings.sentiment_eval_dataset_file or str(default_gold_dataset_path())


def _load_samples_or_error(
    dataset_path: str,
) -> tuple[list[SentimentGoldSample] | None, SentimentEvalResponse | None]:
    """加载金标样本；失败/缺失时返回 (samples, error_response)，二选一非 None。"""
    try:
        samples = load_gold_samples(dataset_path)
    except InvalidGoldSampleError as exc:
        return None, SentimentEvalResponse(
            available=False,
            dataset_path=dataset_path,
            sample_count=0,
            note=f"金标数据集非法：{exc}",
        )

    if not samples:
        return None, SentimentEvalResponse(
            available=False,
            dataset_path=dataset_path,
            sample_count=0,
            note="金标数据集缺失或为空，请先准备 sentiment 金标文件。",
        )

    return samples, None


@router.get("/sentiment", response_model=SentimentEvalResponse)
def get_sentiment_eval(session: Session = Depends(get_db_session)) -> SentimentEvalResponse:
    """只读回放最近一个 batch 的持久化评测结果 + 历史 + 回归对比，不再触发计算。

    金标缺失/非法时降级为 available=False；金标存在但库里还没有任何评测记录时
    available=True 且 primary=None，note 提示去点"重新评测"。
    """
    dataset_path = _resolve_dataset_path()
    samples, error_response = _load_samples_or_error(dataset_path)
    if error_response is not None:
        return error_response

    llm_available = LLMProviderConfigRepository(session).get_active() is not None
    repo = SentimentEvalRunRepository(session)
    latest_batch = repo.get_latest_batch()

    if not latest_batch:
        return SentimentEvalResponse(
            available=True,
            dataset_path=dataset_path,
            sample_count=len(samples),
            primary=None,
            comparison=None,
            note="尚无评测记录，请点击重新评测。",
            evaluated_at=None,
            runs=[],
            llm_available=llm_available,
            history=[],
            regression=None,
        )

    runs = [deserialize_run(row) for row in latest_batch]
    primary = next((run for run in runs if run.model_name == "rule-baseline"), runs[0])
    comparison = pick_comparison(runs)

    previous_batch = repo.get_previous_batch_for_dataset_hash(
        dataset_hash=latest_batch[0].dataset_hash,
        exclude_batch_id=latest_batch[0].batch_id,
        search_limit=_REGRESSION_HISTORY_LIMIT,
    )
    regression, _other_regressed = compute_regression(
        previous_batch=previous_batch, current_runs=runs
    )

    history = build_history(repo.list_recent_batches(limit=_REGRESSION_HISTORY_LIMIT))

    return SentimentEvalResponse(
        available=True,
        dataset_path=dataset_path,
        sample_count=len(samples),
        primary=primary,
        comparison=comparison,
        note=latest_batch[0].note,
        evaluated_at=evaluated_at_of(latest_batch),
        runs=runs,
        llm_available=llm_available,
        history=history,
        regression=regression,
    )


@router.post("/sentiment/run", response_model=SentimentEvalResponse)
def run_sentiment_eval(session: Session = Depends(get_db_session)) -> SentimentEvalResponse:
    """执行一次真实评测（rule-baseline 永远评；有激活 LLM 配置时追加 llm/hybrid，否则
    降级为规则阈值 legacy A/B），落库为一个 batch，返回完整 SentimentEvalResponse。
    """
    dataset_path = _resolve_dataset_path()
    samples, error_response = _load_samples_or_error(dataset_path)
    if error_response is not None:
        return error_response

    dataset_hash = compute_dataset_hash(dataset_path)
    classifier = NewsSignalClassifier(session)
    active_config = LLMProviderConfigRepository(session).get_active()
    llm_available = active_config is not None

    rule_baseline_fn = build_rule_sentiment_classifier(
        classifier, positive_threshold=0.2, negative_threshold=-0.2
    )
    rule_baseline_run = run_sentiment_evaluation(
        samples, model_name="rule-baseline", classify_fn=rule_baseline_fn
    )
    runs: list[SentimentModelRun] = [rule_baseline_run]
    run_configs: dict[str, dict[str, object]] = {
        "rule-baseline": {"positive_threshold": 0.2, "negative_threshold": -0.2}
    }
    note_parts: list[str] = []
    comparison: SentimentABComparison | None

    if active_config is not None:
        model_label = f"{active_config.provider_name}/{active_config.model_name}"

        llm_classifier = NewsSentimentLLMClassifier(config=active_config, rule_fallback=rule_baseline_fn)
        llm_run = run_sentiment_evaluation(
            samples, model_name=f"llm:{model_label}", classify_fn=llm_classifier.classify
        )
        runs.append(llm_run)
        run_configs[llm_run.model_name] = {
            "provider": active_config.provider_name,
            "model": active_config.model_name,
            "cache_scope": SENTIMENT_EVAL_CACHE_SCOPE,
        }
        if llm_classifier.fallback_count:
            note_parts.append(
                f"{llm_run.model_name} 单样本 LLM 分类失败回退规则 "
                f"{llm_classifier.fallback_count}/{llm_classifier.call_count} 次"
            )

        hybrid_fn = build_hybrid_sentiment_classifier(classifier)
        hybrid_run = run_sentiment_evaluation(
            samples, model_name=f"hybrid:{model_label}", classify_fn=hybrid_fn
        )
        runs.append(hybrid_run)
        run_configs[hybrid_run.model_name] = {
            "provider": active_config.provider_name,
            "model": active_config.model_name,
            "allow_llm": True,
        }
        if classifier.llm_refine_failure_count:
            note_parts.append(
                f"{hybrid_run.model_name} 生产路径 LLM 精修失败回退规则 "
                f"{classifier.llm_refine_failure_count} 次"
            )

        comparison = compare_sentiment_runs(rule_baseline_run, llm_run)
    else:
        sensitive_fn = build_rule_sentiment_classifier(
            classifier, positive_threshold=0.1, negative_threshold=-0.1
        )
        sensitive_run = run_sentiment_evaluation(
            samples, model_name="rule-sensitive (±0.10)", classify_fn=sensitive_fn
        )
        runs.append(sensitive_run)
        run_configs[sensitive_run.model_name] = {
            "positive_threshold": 0.1,
            "negative_threshold": -0.1,
        }
        note_parts.append("未配置 LLM，仅规则阈值对比")
        comparison = compare_sentiment_runs(rule_baseline_run, sensitive_run)

    batch_id = str(uuid4())
    evaluated_at = datetime.now(UTC)

    repo = SentimentEvalRunRepository(session)
    previous_batch = repo.get_previous_batch_for_dataset_hash(
        dataset_hash=dataset_hash,
        exclude_batch_id=batch_id,
        search_limit=_REGRESSION_HISTORY_LIMIT,
    )
    regression, other_regressed = compute_regression(previous_batch=previous_batch, current_runs=runs)
    if other_regressed:
        others_desc = "、".join(
            f"{item.model_name}({item.delta:+.4f})" for item in other_regressed
        )
        note_parts.append(f"另有模型 macro_f1 回归：{others_desc}")

    overall_note = "；".join(note_parts) if note_parts else None

    for run in runs:
        storage = serialize_run_for_storage(run)
        repo.add_run(
            batch_id=batch_id,
            created_at=evaluated_at,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            sample_count=len(samples),
            model_name=storage["model_name"],
            config_json=json.dumps(run_configs.get(run.model_name, {}), ensure_ascii=False),
            accuracy=storage["accuracy"],
            macro_f1=storage["macro_f1"],
            importance_weighted_accuracy=storage["importance_weighted_accuracy"],
            per_label_json=storage["per_label_json"],
            confusion_json=storage["confusion_json"],
            note=overall_note,
        )

    history = build_history(repo.list_recent_batches(limit=_REGRESSION_HISTORY_LIMIT))

    return SentimentEvalResponse(
        available=True,
        dataset_path=dataset_path,
        sample_count=len(samples),
        primary=rule_baseline_run,
        comparison=comparison,
        note=overall_note,
        evaluated_at=evaluated_at,
        runs=runs,
        llm_available=llm_available,
        history=history,
        regression=regression,
    )
