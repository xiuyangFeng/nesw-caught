from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.schemas.sentiment_eval import SentimentGoldSample


class DuplicateSampleIdError(ValueError):
    pass


class InvalidGoldSampleError(ValueError):
    pass


def default_gold_dataset_path() -> Path:
    """内置金标数据集路径（backend/data/research/sentiment_gold_benchmark.json）。"""
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "research"
        / "sentiment_gold_benchmark.json"
    )


def load_gold_samples(path: str | Path) -> list[SentimentGoldSample]:
    """加载金标数据集。

    - 文件不存在时返回空列表（数据缺失降级，交由上层判断是否可评）。
    - 支持两种 JSON 结构：顶层数组，或 {"samples": [...]} 包裹。
    - 单条样本非法（缺字段/标签越界/文本为空）会抛 InvalidGoldSampleError。
    - sample_id 重复抛 DuplicateSampleIdError。
    """
    input_path = Path(path)
    if not input_path.exists():
        return []

    raw_text = input_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise InvalidGoldSampleError(f"gold dataset is not valid json: {exc}") from exc

    if isinstance(payload, dict):
        payload = payload.get("samples", [])
    if not isinstance(payload, list):
        raise InvalidGoldSampleError("gold dataset must be a json array or {'samples': [...]}")

    seen_ids: set[str] = set()
    samples: list[SentimentGoldSample] = []
    for raw in payload:
        try:
            sample = SentimentGoldSample.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 - 统一转成领域异常
            raise InvalidGoldSampleError(f"invalid gold sample: {exc}") from exc
        if sample.sample_id in seen_ids:
            raise DuplicateSampleIdError(f"duplicate sample_id: {sample.sample_id}")
        seen_ids.add(sample.sample_id)
        samples.append(sample)
    return samples


def save_gold_samples(
    path: str | Path,
    samples: Iterable[dict[str, object] | SentimentGoldSample],
) -> None:
    """把金标样本写成 JSON 数组文件（供人工维护/测试构造）。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    normalized: list[dict[str, object]] = []
    for raw in samples:
        sample = raw if isinstance(raw, SentimentGoldSample) else SentimentGoldSample.model_validate(raw)
        if sample.sample_id in seen_ids:
            raise DuplicateSampleIdError(f"duplicate sample_id: {sample.sample_id}")
        seen_ids.add(sample.sample_id)
        normalized.append(sample.model_dump(mode="json"))

    output_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
