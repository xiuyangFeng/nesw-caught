"""对 sample_sentiment_dataset.py 产出的候选做情绪预标注，产出待人工复核的 JSONL。

优先用当前激活的 LLM provider（复用 app.repositories.llm_provider_config_repository /
app.services.llm_providers 现有的取激活配置方式，与 news_relevance_annotation.py 的
用法一致：LLMProviderConfigRepository(session).get_active() + build_provider(config).generate_text(...)）。

未配置 LLM，或单条 LLM 调用失败时，回退到规则分类器 NewsSignalClassifier
（allow_llm=False，保证离线可复现），并标记 annotator="rule"。

逐条容错：单条样本（LLM 与规则兜底都失败，理论上只在数据本身非法时发生）
直接跳过并计数，不让一条脏数据拖垮整批。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, Field, model_validator

from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import build_provider
from app.services.news_signal_classifier import NewsSignalClassifier
from scripts.sentiment_dataset_lib import (
    SentimentAnnotation,
    SentimentCandidate,
    SentimentLabel,
    read_jsonl,
    write_jsonl,
)

DEFAULT_BODY_PROMPT_CHARS = 1500

SENTIMENT_SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier for stock market read-throughs. "
    "Return JSON only with keys: sentiment_label, sentiment_score, reason. "
    "sentiment_label must be exactly one of: positive, negative, neutral. "
    "sentiment_score is a number from -1 (very bearish) to 1 (very bullish). "
    "reason is a short one-sentence explanation, written in Chinese."
)


class _SentimentPrediction(BaseModel):
    sentiment_label: SentimentLabel
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    reason: str

    @model_validator(mode="after")
    def _validate_reason(self) -> _SentimentPrediction:
        if not self.reason.strip():
            raise ValueError("reason is required")
        return self


@dataclass
class AnnotationStats:
    llm_success: int = 0
    llm_failed: int = 0
    rule_used: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.llm_success + self.rule_used


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


def _build_prompts(candidate: SentimentCandidate) -> tuple[str, str]:
    user_prompt = "\n".join(
        [
            f"Market: {candidate.market}",
            f"Title: {candidate.title}",
            f"Summary: {candidate.summary or ''}",
            f"Body: {(candidate.body or '')[:DEFAULT_BODY_PROMPT_CHARS]}",
        ]
    )
    return SENTIMENT_SYSTEM_PROMPT, user_prompt


def annotate_with_llm(candidate: SentimentCandidate, provider: Any) -> SentimentAnnotation:
    system_prompt, user_prompt = _build_prompts(candidate)
    content = provider.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)
    payload = _extract_json_payload(content)
    try:
        prediction = _SentimentPrediction.model_validate_json(payload)
    except Exception as exc:  # noqa: BLE001 - 统一转成可捕获异常，交给上层回退规则分类器
        raise ValueError(f"llm returned invalid sentiment prediction payload: {exc}") from exc

    return SentimentAnnotation(
        **candidate.model_dump(),
        predicted_label=prediction.sentiment_label,
        predicted_score=prediction.sentiment_score,
        reason=prediction.reason,
        annotator="llm",
        status="pending",
    )


def annotate_with_rule(candidate: SentimentCandidate, classifier: Any) -> SentimentAnnotation:
    result = classifier.classify(
        title=candidate.title,
        summary=candidate.summary,
        body=candidate.body,
        allow_llm=False,
    )
    score = max(-1.0, min(1.0, result.sentiment_score))
    reason = f"规则分类器关键词加权打分 {score:+.2f}，据此判定为 {result.sentiment_label}。"
    return SentimentAnnotation(
        **candidate.model_dump(),
        predicted_label=result.sentiment_label,
        predicted_score=score,
        reason=reason,
        annotator="rule",
        status="pending",
    )


def annotate_candidates(
    candidates: Sequence[SentimentCandidate],
    *,
    active_config: Any | None,
    rule_classifier: Any,
    provider_factory: Callable[[Any], Any] = build_provider,
) -> tuple[list[SentimentAnnotation], AnnotationStats]:
    stats = AnnotationStats()
    provider = provider_factory(active_config) if active_config is not None else None

    annotations: list[SentimentAnnotation] = []
    for candidate in candidates:
        try:
            if provider is not None:
                try:
                    annotation = annotate_with_llm(candidate, provider)
                    stats.llm_success += 1
                    annotations.append(annotation)
                    continue
                except Exception:  # noqa: BLE001 - LLM 失败回退规则分类器，单条不阻断整批
                    stats.llm_failed += 1

            annotation = annotate_with_rule(candidate, rule_classifier)
            stats.rule_used += 1
            annotations.append(annotation)
        except Exception:  # noqa: BLE001 - 规则兜底也失败（数据本身非法）：跳过并计数
            stats.skipped += 1
            continue

    return annotations, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="对情绪候选样本做 LLM/规则预标注，产出待复核 JSONL。")
    parser.add_argument("input", type=Path, help="sample_sentiment_dataset.py 产出的候选 JSONL")
    parser.add_argument("output", type=Path, help="待复核 JSONL 输出路径")
    args = parser.parse_args()

    candidates = read_jsonl(args.input, SentimentCandidate)
    if not candidates:
        print(f"{args.input} 中没有候选样本，退出。")
        return

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        active_config = LLMProviderConfigRepository(session).get_active()
        rule_classifier = NewsSignalClassifier(session)
        annotations, stats = annotate_candidates(
            candidates,
            active_config=active_config,
            rule_classifier=rule_classifier,
        )

    write_jsonl(args.output, annotations)
    print(
        f"annotated {len(annotations)} samples -> {args.output} "
        f"(llm_ok={stats.llm_success}, llm_failed={stats.llm_failed}, "
        f"rule={stats.rule_used}, skipped={stats.skipped})"
    )


if __name__ == "__main__":
    main()
