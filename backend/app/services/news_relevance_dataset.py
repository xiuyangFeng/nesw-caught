from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.schemas.research import MarketRelevanceSample


class DuplicateSampleIdError(ValueError):
    pass


class InvalidBenchmarkSampleError(ValueError):
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
