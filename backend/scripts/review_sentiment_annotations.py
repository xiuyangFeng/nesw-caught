"""终端逐条复核情绪预标注，确认后合并进金标数据集。

读 annotate_sentiment_dataset.py 产出的待复核 JSONL，逐条展示标题/摘要/预标注，
人工输入：
  y        接受预标注标签
  p/n/u    改标为 positive/negative/neutral
  s        跳过（不进金标）
  q        退出并保存已复核的部分

确认（接受或改标）的样本转换成 app.schemas.sentiment_eval.SentimentGoldSample，
sample_id 规则为 gold-<news_id>，与 --output 指定文件里已有的金标样本按
sample_id/news_id 去重合并后，经 save_gold_samples() 落盘。默认输出路径是
backend/data/research/sentiment_gold_dataset.json —— 不会覆盖内置演示集
sentiment_gold_benchmark.json。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_dataset import load_gold_samples, save_gold_samples
from scripts.sentiment_dataset_lib import SentimentAnnotation, SentimentLabel, read_jsonl

DEFAULT_GOLD_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "sentiment_gold_dataset.json"

_DECISION_LABELS: dict[str, SentimentLabel] = {"p": "positive", "n": "negative", "u": "neutral"}
_MIN_IMPORTANCE = 0.3


class ReviewQuit(Exception):
    """复核者输入 q，提前结束本轮复核（已确认的部分仍会保存）。"""


def apply_review_decision(annotation: SentimentAnnotation, decision: str) -> SentimentAnnotation:
    """把一次终端输入应用到预标注样本，返回带 status 的新样本。

    y / 空输入 -> 接受预标注标签；p/n/u -> 改标；s -> 跳过；q -> 抛 ReviewQuit。
    """
    normalized = decision.strip().lower()
    if normalized in {"y", ""}:
        return annotation.model_copy(update={"status": "accepted", "reviewed_label": annotation.predicted_label})
    if normalized in _DECISION_LABELS:
        return annotation.model_copy(
            update={"status": "accepted", "reviewed_label": _DECISION_LABELS[normalized]}
        )
    if normalized == "s":
        return annotation.model_copy(update={"status": "skipped", "reviewed_label": None})
    if normalized == "q":
        raise ReviewQuit()
    raise ValueError(f"无法识别的输入: {decision!r}（合法输入：y/p/n/u/s/q）")


def annotation_to_gold_sample(annotation: SentimentAnnotation) -> SentimentGoldSample:
    """把复核确认过的预标注样本转换成金标样本。

    importance 用 |predicted_score| 作为默认重要度估计（越极端的情绪打分通常
    对应越明确的利好/利空事件），并设一个下限避免中性样本权重掉到 0。
    """
    label = annotation.reviewed_label or annotation.predicted_label
    importance = round(max(_MIN_IMPORTANCE, min(1.0, abs(annotation.predicted_score))), 2)
    return SentimentGoldSample(
        sample_id=f"gold-{annotation.news_id}",
        text=annotation.title,
        sentiment_label=label,
        title=annotation.title,
        summary=annotation.summary,
        body=annotation.body,
        market=annotation.market,
        news_id=annotation.news_id,
        importance=importance,
    )


def merge_gold_samples(
    existing: Iterable[SentimentGoldSample],
    new_samples: Iterable[SentimentGoldSample],
) -> list[SentimentGoldSample]:
    """按 sample_id 追加/覆盖合并，并按 news_id 去重（同一条新闻不会重复入库）。"""
    by_sample_id: dict[str, SentimentGoldSample] = {sample.sample_id: sample for sample in existing}
    seen_news_ids = {sample.news_id for sample in by_sample_id.values() if sample.news_id is not None}

    for sample in new_samples:
        if (
            sample.news_id is not None
            and sample.news_id in seen_news_ids
            and sample.sample_id not in by_sample_id
        ):
            # 同一条新闻已经以另一个 sample_id 存在（legacy 手写样本等），跳过避免重复内容。
            continue
        by_sample_id[sample.sample_id] = sample
        if sample.news_id is not None:
            seen_news_ids.add(sample.news_id)

    return list(by_sample_id.values())


def run_review_session(
    annotations: Sequence[SentimentAnnotation],
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> list[SentimentAnnotation]:
    """逐条跑复核循环，返回已经打上 accepted/skipped 状态的样本（q 会提前结束）。"""
    reviewed: list[SentimentAnnotation] = []
    total = len(annotations)
    for index, annotation in enumerate(annotations, start=1):
        print_fn(f"[{index}/{total}] {annotation.title}")
        print_fn(f"  市场: {annotation.market}  来源标签: {annotation.existing_sentiment_label or '(无)'}")
        print_fn(f"  摘要: {annotation.summary or '(无)'}")
        print_fn(
            f"  预标注: {annotation.predicted_label} "
            f"(score={annotation.predicted_score:+.2f}, by={annotation.annotator})"
        )
        print_fn(f"  理由: {annotation.reason}")

        while True:
            raw = input_fn("  确认[y] 改标[p/n/u] 跳过[s] 退出[q]: ")
            try:
                decided = apply_review_decision(annotation, raw)
            except ReviewQuit:
                return reviewed
            except ValueError as exc:
                print_fn(f"  {exc}")
                continue
            reviewed.append(decided)
            break

    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description="终端逐条复核情绪预标注，确认后合并进金标数据集。")
    parser.add_argument("input", type=Path, help="annotate_sentiment_dataset.py 产出的待复核 JSONL")
    parser.add_argument("--output", type=Path, default=DEFAULT_GOLD_OUTPUT_PATH, help="金标数据集输出路径")
    args = parser.parse_args()

    annotations = read_jsonl(args.input, SentimentAnnotation)
    if not annotations:
        print(f"{args.input} 中没有待复核样本，退出。")
        return

    reviewed = run_review_session(annotations)
    accepted = [item for item in reviewed if item.status == "accepted"]
    skipped_count = len(reviewed) - len(accepted)

    if not accepted:
        print(f"复核了 {len(reviewed)} 条，全部跳过，未写入金标数据集。")
        return

    new_gold_samples = [annotation_to_gold_sample(item) for item in accepted]
    existing = load_gold_samples(args.output)
    merged = merge_gold_samples(existing, new_gold_samples)
    save_gold_samples(args.output, merged)

    print(
        f"复核了 {len(reviewed)} 条（接受 {len(accepted)}，跳过 {skipped_count}），"
        f"合并后金标数据集共 {len(merged)} 条 -> {args.output}"
    )


if __name__ == "__main__":
    main()
