from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable
from pathlib import Path

from app.schemas.research import (
    MarketRelevanceAnnotation,
    MarketRelevanceLabel,
    MarketRelevanceSample,
)


class DuplicateSampleIdError(ValueError):
    pass


class InvalidBenchmarkSampleError(ValueError):
    pass


class MissingReviewedSampleError(ValueError):
    pass


class InvalidReviewDecisionError(ValueError):
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


def export_review_samples_markdown(samples: Iterable[dict[str, object] | MarketRelevanceSample]) -> str:
    normalized = [
        sample if isinstance(sample, MarketRelevanceSample) else MarketRelevanceSample.model_validate(sample)
        for sample in samples
    ]
    lines = [
        "# Market Relevance Review Queue",
        "",
        f"Total samples: {len(normalized)}",
        "",
        "For each sample:",
        "- Confirm or correct `labels.market_relevant`",
        "- If not relevant, confirm or correct `labels.noise_type`",
        "- Set `annotation.label_source` to `human_reviewed` or `human_corrected`",
        "",
    ]

    for index, sample in enumerate(normalized, start=1):
        model_label = "relevant" if sample.labels.market_relevant else f"not relevant (`{sample.labels.noise_type}`)"
        lines.extend(
            [
                f"## {index}. {sample.sample_id}",
                "",
                f"- Title: {sample.content.title}",
                f"- Source: {sample.origin.source_name}",
                f"- URL: {sample.origin.canonical_url}",
                f"- Published At: {sample.origin.published_at.isoformat() if sample.origin.published_at else '(missing)'}",
                f"- Model Label: {model_label}",
                f"- Confidence: {sample.annotation.confidence:.2f}",
                "- Review Action: set `annotation.label_source` to `human_reviewed` or `human_corrected`",
                f"- Model Reason: {sample.annotation.review_notes or '(none)'}",
                f"- Summary: {sample.content.summary or '(missing)'}",
                f"- Body Excerpt: {sample.content.body_excerpt or '(missing)'}",
                "",
            ]
        )
    return "\n".join(lines)


def export_review_samples_csv(samples: Iterable[dict[str, object] | MarketRelevanceSample]) -> str:
    normalized = [
        sample if isinstance(sample, MarketRelevanceSample) else MarketRelevanceSample.model_validate(sample)
        for sample in samples
    ]
    fieldnames = [
        "sample_id",
        "source_type",
        "source_name",
        "canonical_url",
        "published_at",
        "title",
        "summary",
        "body_excerpt",
        "model_market_relevant",
        "model_noise_type",
        "model_confidence",
        "model_reason",
        "review_market_relevant",
        "review_noise_type",
        "review_label_source",
        "review_notes",
    ]
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for sample in normalized:
        writer.writerow(
            {
                "sample_id": sample.sample_id,
                "source_type": sample.source_type,
                "source_name": sample.origin.source_name,
                "canonical_url": sample.origin.canonical_url,
                "published_at": sample.origin.published_at.isoformat() if sample.origin.published_at else "",
                "title": sample.content.title,
                "summary": sample.content.summary or "",
                "body_excerpt": sample.content.body_excerpt or "",
                "model_market_relevant": "true" if sample.labels.market_relevant else "false",
                "model_noise_type": sample.labels.noise_type or "",
                "model_confidence": f"{sample.annotation.confidence:.2f}",
                "model_reason": sample.annotation.review_notes,
                "review_market_relevant": "",
                "review_noise_type": "",
                "review_label_source": "",
                "review_notes": "",
            }
        )
    return buffer.getvalue()


def import_review_decisions_csv(
    review_queue_path: str | Path,
    csv_path: str | Path,
    output_path: str | Path,
) -> list[MarketRelevanceSample]:
    samples = _load_samples(review_queue_path)
    by_id = {sample.sample_id: sample for sample in samples}
    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    imported: list[MarketRelevanceSample] = []
    seen_ids: set[str] = set()
    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if sample_id not in by_id:
            raise InvalidReviewDecisionError(f"sample_id not found in review queue: {sample_id}")
        if sample_id in seen_ids:
            raise InvalidReviewDecisionError(f"duplicate sample_id in review CSV: {sample_id}")
        seen_ids.add(sample_id)
        sample = by_id[sample_id]
        label_source = (row.get("review_label_source") or "").strip()
        if label_source not in {"human_reviewed", "human_corrected"}:
            raise InvalidReviewDecisionError(
                f"review_label_source must be human_reviewed or human_corrected for sample {sample_id}"
            )

        market_relevant = _parse_optional_bool(row.get("review_market_relevant"))
        if market_relevant is None:
            market_relevant = sample.labels.market_relevant
        noise_type = (row.get("review_noise_type") or "").strip() or sample.labels.noise_type
        if market_relevant:
            noise_type = None
        elif noise_type is None:
            raise InvalidReviewDecisionError(f"noise_type is required for non-relevant sample {sample_id}")

        review_notes = (row.get("review_notes") or "").strip() or sample.annotation.review_notes
        imported.append(
            sample.model_copy(
                update={
                    "labels": MarketRelevanceLabel(
                        market_relevant=market_relevant,
                        noise_type=noise_type,
                    ),
                    "annotation": MarketRelevanceAnnotation(
                        label_source=label_source,
                        model_name=sample.annotation.model_name,
                        confidence=sample.annotation.confidence,
                        review_notes=review_notes,
                    ),
                }
            )
        )

    missing_ids = [sample.sample_id for sample in samples if sample.sample_id not in seen_ids]
    if missing_ids:
        raise InvalidReviewDecisionError(
            f"review CSV is missing decisions for sample_id: {', '.join(missing_ids[:5])}"
        )

    ordered = _order_by_sample_id(samples, imported)
    save_samples(output_path, ordered)
    return ordered


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


def _order_by_sample_id(
    reference_samples: list[MarketRelevanceSample],
    updated_samples: list[MarketRelevanceSample],
) -> list[MarketRelevanceSample]:
    by_id = {sample.sample_id: sample for sample in updated_samples}
    return [by_id[sample.sample_id] for sample in reference_samples if sample.sample_id in by_id]


def _parse_optional_bool(value: str | None) -> bool | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise InvalidReviewDecisionError(f"invalid boolean value: {value}")


def _requires_review(sample: MarketRelevanceSample, *, low_confidence_threshold: float) -> bool:
    if sample.annotation.confidence < low_confidence_threshold:
        return True
    if sample.labels.noise_type == "other":
        return True
    title = sample.content.title.strip()
    summary = (sample.content.summary or "").strip()
    return len(title) < 12 or not summary
