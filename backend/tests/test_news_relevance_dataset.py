from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.news_item import NewsItem
from app.services.news_ingestion import SourceDefinition
from app.services.news_relevance_dataset import (
    DuplicateSampleIdError,
    InvalidBenchmarkSampleError,
    merge_reviewed_samples,
    load_benchmark_samples,
    save_samples,
)


def _sample_payload(*, sample_id: str, label_source: str = "human_reviewed") -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source_type": "historical",
        "origin": {
            "news_id": 1,
            "source_name": "Reuters",
            "canonical_url": f"https://example.com/{sample_id}",
            "published_at": "2026-03-25T00:00:00Z",
        },
        "content": {
            "title": f"Sample {sample_id}",
            "summary": "Market-moving update.",
            "body_excerpt": None,
        },
        "labels": {
            "market_relevant": True,
            "noise_type": None,
        },
        "annotation": {
            "label_source": label_source,
            "model_name": "deepseek-chat",
            "confidence": 0.93,
            "review_notes": "",
        },
    }


def test_save_samples_rejects_duplicate_sample_ids(tmp_path) -> None:
    path = tmp_path / "samples.jsonl"
    samples = [_sample_payload(sample_id="dup-1"), _sample_payload(sample_id="dup-1")]

    with pytest.raises(DuplicateSampleIdError):
        save_samples(path, samples)


def test_load_benchmark_samples_rejects_model_only_labels(tmp_path) -> None:
    path = tmp_path / "benchmark.jsonl"
    path.write_text(json.dumps(_sample_payload(sample_id="model-only", label_source="model_only")) + "\n", encoding="utf-8")

    with pytest.raises(InvalidBenchmarkSampleError):
        load_benchmark_samples(path)


def test_merge_reviewed_samples_only_promotes_reviewed_rows(tmp_path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    benchmark_path = tmp_path / "benchmark.jsonl"
    save_samples(
        candidates_path,
        [
            _sample_payload(sample_id="reviewed", label_source="human_reviewed"),
            _sample_payload(sample_id="model-only", label_source="model_only"),
        ],
    )

    promoted = merge_reviewed_samples(candidates_path, benchmark_path)

    assert promoted == 1
    benchmark_samples = load_benchmark_samples(benchmark_path)
    assert [sample.sample_id for sample in benchmark_samples] == ["reviewed"]


def test_merge_reviewed_samples_preserves_existing_benchmark_rows(tmp_path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    benchmark_path = tmp_path / "benchmark.jsonl"
    save_samples(benchmark_path, [_sample_payload(sample_id="existing", label_source="human_reviewed")])
    save_samples(candidates_path, [_sample_payload(sample_id="new-reviewed", label_source="human_reviewed")])

    promoted = merge_reviewed_samples(candidates_path, benchmark_path)

    assert promoted == 1
    benchmark_samples = load_benchmark_samples(benchmark_path)
    assert [sample.sample_id for sample in benchmark_samples] == ["existing", "new-reviewed"]


def _load_sampling_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "sample_market_relevance_dataset.py"
    spec = importlib.util.spec_from_file_location("sample_market_relevance_dataset", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_news_item(*, news_id: int, source_name: str, canonical_url: str, fetched_at: datetime) -> NewsItem:
    return NewsItem(
        id=news_id,
        source_name=source_name,
        source_url=f"https://{source_name.lower().replace(' ', '')}.example.com/feed",
        title=f"{source_name} headline {news_id}",
        summary=f"Summary {news_id}",
        canonical_url=canonical_url,
        url_hash=sha256(canonical_url.encode("utf-8")).hexdigest(),
        market="us",
        language="en",
        sentiment_label=None,
        sentiment_score=None,
        published_at=fetched_at,
        fetched_at=fetched_at,
        ingest_status="ingested",
    )


def test_sampling_script_preserves_historical_and_realtime_mix(tmp_path, monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    module = _load_sampling_module()

    with session_local() as session:
        session.add_all(
            [
                _make_news_item(
                    news_id=1,
                    source_name="Legacy Feed",
                    canonical_url="https://example.com/legacy-1",
                    fetched_at=datetime(2025, 3, 17, 1, 0, tzinfo=timezone.utc),
                ),
                _make_news_item(
                    news_id=2,
                    source_name="Legacy Feed",
                    canonical_url="https://example.com/legacy-2",
                    fetched_at=datetime(2025, 3, 17, 2, 0, tzinfo=timezone.utc),
                ),
                _make_news_item(
                    news_id=3,
                    source_name="Realtime Feed",
                    canonical_url="https://example.com/realtime-1",
                    fetched_at=datetime(2025, 3, 18, 1, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

        monkeypatch.setattr(
            module,
            "load_sources",
            lambda: [SourceDefinition(name="Realtime Feed", source_type="rss", url="https://example.com/rss", market="us")],
        )

        records = module.build_market_relevance_candidates(session, historical_limit=2, realtime_limit=1)
        output_path = tmp_path / "market_relevance_candidates.jsonl"
        module.write_market_relevance_candidates(records, output_path)

    assert [record.source_type for record in records] == ["historical", "historical", "realtime"]
    assert [record.origin.canonical_url for record in records] == [
        "https://example.com/legacy-1",
        "https://example.com/legacy-2",
        "https://example.com/realtime-1",
    ]

    persisted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [sample["source_type"] for sample in persisted] == ["historical", "historical", "realtime"]


def test_sampling_script_deduplicates_canonical_urls_across_pools(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    module = _load_sampling_module()
    shared_url = "https://example.com/shared-story"

    with session_local() as session:
        session.add(
            _make_news_item(
                news_id=11,
                source_name="Realtime Feed",
                canonical_url=shared_url,
                fetched_at=datetime(2025, 3, 18, 1, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        monkeypatch.setattr(
            module,
            "load_sources",
            lambda: [SourceDefinition(name="Realtime Feed", source_type="rss", url="https://example.com/rss", market="us")],
        )
        records = module.build_market_relevance_candidates(session, historical_limit=1, realtime_limit=1)

    assert len(records) == 1
    assert records[0].origin.canonical_url == shared_url
    assert records[0].source_type == "historical"
