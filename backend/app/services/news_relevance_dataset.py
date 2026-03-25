from __future__ import annotations

import json
from pathlib import Path
import random
from typing import Iterable

from app.schemas.research import MarketRelevanceSample


class DuplicateSampleIdError(ValueError):
    pass


class InvalidBenchmarkSampleError(ValueError):
    pass


class MissingReviewedSampleError(ValueError):
    pass


def save_samples(path: str | Path, samples: Iterable[dict[str, object] | MarketRelevanceSample]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    normalized: list[MarketRelevanceSample] = []
    for raw in samples:
        sample = raw if isinstance(raw, MarketRelevanceSample) else MarketRelevanceSample.model_validate(raw)
        if sample.sample_id in seen_ids:
            raise DuplicateSampleIdError(f"duplicate sample_id: {sample.sample_id}")
        seen_ids.add(sample.sample_id)
        normalized.append(sample)

    with output_path.open("w", encoding="utf-8") as handle:
        for sample in normalized:
            handle.write(sample.model_dump_json())
            handle.write("\n")


def load_benchmark_samples(path: str | Path) -> list[MarketRelevanceSample]:
    samples = _load_samples(path)
    for sample in samples:
        if sample.annotation.label_source not in {"human_reviewed", "human_corrected"}:
            raise InvalidBenchmarkSampleError(
                f"benchmark sample {sample.sample_id} must be human reviewed or corrected"
            )
    return samples


def merge_reviewed_samples(candidates_path: str | Path, benchmark_path: str | Path) -> int:
    candidates = _load_samples(candidates_path)
    existing = _load_samples(benchmark_path)
    reviewed = [
        sample
        for sample in candidates
        if sample.annotation.label_source in {"human_reviewed", "human_corrected"}
    ]
    merged: dict[str, MarketRelevanceSample] = {sample.sample_id: sample for sample in existing}
    for sample in reviewed:
        merged[sample.sample_id] = sample
    save_samples(benchmark_path, merged.values())
    return len(reviewed)


def select_review_samples(
    samples: Iterable[dict[str, object] | MarketRelevanceSample],
    *,
    low_confidence_threshold: float = 0.75,
    spot_check_count_per_bucket: int = 10,
    rng_seed: int = 0,
) -> list[MarketRelevanceSample]:
    normalized = [
        sample if isinstance(sample, MarketRelevanceSample) else MarketRelevanceSample.model_validate(sample)
        for sample in samples
    ]
    mandatory: list[MarketRelevanceSample] = []
    high_confidence_positive: list[MarketRelevanceSample] = []
    high_confidence_negative: list[MarketRelevanceSample] = []

    for sample in normalized:
        if sample.annotation.label_source != "model_only":
            continue
        if _requires_review(sample, low_confidence_threshold=low_confidence_threshold):
            mandatory.append(sample)
            continue
        if sample.labels.market_relevant:
            high_confidence_positive.append(sample)
        else:
            high_confidence_negative.append(sample)

    rng = random.Random(rng_seed)
    selected: dict[str, MarketRelevanceSample] = {sample.sample_id: sample for sample in mandatory}
    for bucket in (high_confidence_positive, high_confidence_negative):
        chosen = list(bucket)
        rng.shuffle(chosen)
        for sample in chosen[:spot_check_count_per_bucket]:
            selected[sample.sample_id] = sample
    return list(selected.values())


def apply_reviewed_samples(
    candidates_path: str | Path,
    reviewed_path: str | Path,
    benchmark_path: str | Path,
) -> int:
    candidates = _load_samples(candidates_path)
    reviewed_samples = _load_samples(reviewed_path)
    reviewed_by_id = {sample.sample_id: sample for sample in reviewed_samples}

    missing = [sample_id for sample_id in reviewed_by_id if sample_id not in {sample.sample_id for sample in candidates}]
    if missing:
        raise MissingReviewedSampleError(f"review samples not found in candidates: {', '.join(sorted(missing))}")

    updated_candidates: list[MarketRelevanceSample] = []
    applied = 0
    for sample in candidates:
        reviewed = reviewed_by_id.get(sample.sample_id)
        if reviewed is None:
            updated_candidates.append(sample)
            continue
        updated_candidates.append(reviewed)
        applied += 1

    save_samples(candidates_path, updated_candidates)
    merge_reviewed_samples(candidates_path, benchmark_path)
    return applied


def _load_samples(path: str | Path) -> list[MarketRelevanceSample]:
    input_path = Path(path)
    if not input_path.exists():
        return []

    samples: list[MarketRelevanceSample] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        samples.append(MarketRelevanceSample.model_validate(json.loads(stripped)))
    return samples


def _requires_review(sample: MarketRelevanceSample, *, low_confidence_threshold: float) -> bool:
    if sample.annotation.confidence < low_confidence_threshold:
        return True
    if sample.labels.noise_type == "other":
        return True
    title = sample.content.title.strip()
    summary = (sample.content.summary or "").strip()
    return len(title) < 12 or not summary
