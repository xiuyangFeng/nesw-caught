from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.sentiment_eval import SentimentEvalResponse
from app.services.news_sentiment_dataset import (
    InvalidGoldSampleError,
    default_gold_dataset_path,
    load_gold_samples,
)
from app.services.news_sentiment_evaluator import build_rule_sentiment_classifier
from app.services.news_sentiment_experiment_runner import run_sentiment_ab
from app.services.news_signal_classifier import NewsSignalClassifier

router = APIRouter()


@router.get("/sentiment", response_model=SentimentEvalResponse)
def get_sentiment_eval(session: Session = Depends(get_db_session)) -> SentimentEvalResponse:
    """对内置金标集即时评一遍，返回单模型指标 + 两套阈值配置的 A/B 对比。

    金标缺失/为空/损坏时降级为 available=False，避免 500。
    """
    settings = get_settings()
    dataset_path = settings.sentiment_eval_dataset_file or str(default_gold_dataset_path())

    try:
        samples = load_gold_samples(dataset_path)
    except InvalidGoldSampleError as exc:
        return SentimentEvalResponse(
            available=False,
            dataset_path=dataset_path,
            sample_count=0,
            note=f"金标数据集非法：{exc}",
        )

    if not samples:
        return SentimentEvalResponse(
            available=False,
            dataset_path=dataset_path,
            sample_count=0,
            note="金标数据集缺失或为空，请先准备 sentiment 金标文件。",
        )

    classifier = NewsSignalClassifier(session)
    # 两套“模型配置”= 同一规则分类器的不同判定阈值，离线确定性可复现。
    baseline_fn = build_rule_sentiment_classifier(
        classifier, positive_threshold=0.2, negative_threshold=-0.2
    )
    sensitive_fn = build_rule_sentiment_classifier(
        classifier, positive_threshold=0.1, negative_threshold=-0.1
    )

    comparison = run_sentiment_ab(
        samples,
        model_a_name="rule-baseline (±0.20)",
        model_a_classify=baseline_fn,
        model_b_name="rule-sensitive (±0.10)",
        model_b_classify=sensitive_fn,
    )

    return SentimentEvalResponse(
        available=True,
        dataset_path=dataset_path,
        sample_count=len(samples),
        primary=comparison.model_a,
        comparison=comparison,
    )
