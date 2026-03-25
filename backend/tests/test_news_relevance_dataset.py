from __future__ import annotations

import csv
import importlib.util
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.services.news_ingestion import SourceDefinition
from app.services.news_relevance_dataset import (
    DuplicateSampleIdError,
    InvalidBenchmarkSampleError,
    InvalidReviewDecisionError,
    apply_reviewed_samples,
    export_review_samples_csv,
    export_review_samples_markdown,
    import_review_decisions_csv,
    merge_reviewed_samples,
    load_benchmark_samples,
    save_samples,
    select_review_samples,
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


def test_select_review_samples_captures_mandatory_and_spot_check_cases() -> None:
    samples = [
        _sample_payload(sample_id="low-confidence", label_source="model_only"),
        _sample_payload(sample_id="other-noise", label_source="model_only"),
        _sample_payload(sample_id="short-title", label_source="model_only"),
        _sample_payload(sample_id="high-confidence-positive", label_source="model_only"),
        _sample_payload(sample_id="high-confidence-negative", label_source="model_only"),
    ]
    samples[0]["annotation"]["confidence"] = 0.42
    samples[1]["labels"] = {"market_relevant": False, "noise_type": "other"}
    samples[2]["content"]["title"] = "Brief"
    samples[2]["content"]["summary"] = ""
    samples[3]["annotation"]["confidence"] = 0.98
    samples[4]["annotation"]["confidence"] = 0.97
    samples[4]["labels"] = {"market_relevant": False, "noise_type": "off_topic"}

    review_samples = select_review_samples(samples, spot_check_count_per_bucket=1, rng_seed=7)

    assert {sample.sample_id for sample in review_samples} == {
        "low-confidence",
        "other-noise",
        "short-title",
        "high-confidence-positive",
        "high-confidence-negative",
    }


def test_apply_reviewed_samples_updates_candidates_and_benchmark(tmp_path) -> None:
    candidates_path = tmp_path / "annotated.jsonl"
    review_path = tmp_path / "review.jsonl"
    benchmark_path = tmp_path / "benchmark.jsonl"
    save_samples(
        candidates_path,
        [
            _sample_payload(sample_id="keep-positive", label_source="model_only"),
            _sample_payload(sample_id="flip-negative", label_source="model_only"),
        ],
    )
    reviewed = [
        _sample_payload(sample_id="keep-positive", label_source="human_reviewed"),
        _sample_payload(sample_id="flip-negative", label_source="human_corrected"),
    ]
    reviewed[1]["labels"] = {"market_relevant": False, "noise_type": "off_topic"}
    save_samples(review_path, reviewed)

    applied = apply_reviewed_samples(candidates_path, review_path, benchmark_path)

    assert applied == 2
    candidate_rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines()]
    assert [row["annotation"]["label_source"] for row in candidate_rows] == ["human_reviewed", "human_corrected"]
    assert candidate_rows[1]["labels"] == {"market_relevant": False, "noise_type": "off_topic"}
    benchmark_rows = [sample.sample_id for sample in load_benchmark_samples(benchmark_path)]
    assert benchmark_rows == ["keep-positive", "flip-negative"]


def test_select_review_samples_skips_already_reviewed_rows() -> None:
    samples = [
        _sample_payload(sample_id="reviewed", label_source="human_reviewed"),
        _sample_payload(sample_id="pending", label_source="model_only"),
    ]
    samples[1]["annotation"]["confidence"] = 0.4

    review_samples = select_review_samples(samples, spot_check_count_per_bucket=1, rng_seed=7)

    assert [sample.sample_id for sample in review_samples] == ["pending"]


def test_export_review_samples_markdown_renders_readable_sections() -> None:
    samples = [
        _sample_payload(sample_id="positive", label_source="model_only"),
        _sample_payload(sample_id="negative", label_source="model_only"),
    ]
    samples[0]["annotation"]["confidence"] = 0.91
    samples[0]["annotation"]["review_notes"] = "Likely market relevant because of clear regulatory impact."
    samples[1]["labels"] = {"market_relevant": False, "noise_type": "generic_tech"}
    samples[1]["annotation"]["confidence"] = 0.66
    samples[1]["annotation"]["review_notes"] = "Looks like generic product chatter."

    rendered = export_review_samples_markdown(samples)

    assert "# Market Relevance Review Queue" in rendered
    assert "## 1. positive" in rendered
    assert "## 2. negative" in rendered
    assert "- Model Label: relevant" in rendered
    assert "- Model Label: not relevant (`generic_tech`)" in rendered
    assert "- Review Action: set `annotation.label_source` to `human_reviewed` or `human_corrected`" in rendered
    assert "Likely market relevant because of clear regulatory impact." in rendered


def test_export_review_samples_csv_writes_editable_columns() -> None:
    samples = [
        _sample_payload(sample_id="positive", label_source="model_only"),
        _sample_payload(sample_id="negative", label_source="model_only"),
    ]
    samples[1]["labels"] = {"market_relevant": False, "noise_type": "generic_tech"}
    samples[1]["annotation"]["review_notes"] = "Generic product chatter."

    rendered = export_review_samples_csv(samples)
    rows = list(csv.DictReader(rendered.splitlines()))

    assert rows[0]["sample_id"] == "positive"
    assert rows[0]["model_market_relevant"] == "true"
    assert rows[0]["review_market_relevant"] == ""
    assert rows[1]["model_noise_type"] == "generic_tech"
    assert rows[1]["model_reason"] == "Generic product chatter."


def test_import_review_decisions_csv_updates_reviewed_samples(tmp_path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    csv_path = tmp_path / "review.csv"
    output_path = tmp_path / "reviewed.jsonl"
    samples = [
        _sample_payload(sample_id="positive", label_source="model_only"),
        _sample_payload(sample_id="negative", label_source="model_only"),
    ]
    samples[1]["labels"] = {"market_relevant": False, "noise_type": "generic_tech"}
    save_samples(queue_path, samples)
    csv_path.write_text(
        "\n".join(
            [
                "sample_id,review_market_relevant,review_noise_type,review_label_source,review_notes",
                "positive,true,,human_reviewed,keep as relevant",
                "negative,false,off_topic,human_corrected,should be off topic",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    imported = import_review_decisions_csv(queue_path, csv_path, output_path)

    assert [sample.annotation.label_source for sample in imported] == ["human_reviewed", "human_corrected"]
    assert imported[0].labels.market_relevant is True
    assert imported[1].labels.noise_type == "off_topic"
    persisted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert persisted[1]["annotation"]["review_notes"] == "should be off topic"


def test_import_review_decisions_csv_rejects_missing_queue_rows(tmp_path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    csv_path = tmp_path / "review.csv"
    output_path = tmp_path / "reviewed.jsonl"
    samples = [
        _sample_payload(sample_id="positive", label_source="model_only"),
        _sample_payload(sample_id="negative", label_source="model_only"),
    ]
    samples[1]["labels"] = {"market_relevant": False, "noise_type": "generic_tech"}
    save_samples(queue_path, samples)
    csv_path.write_text(
        "\n".join(
            [
                "sample_id,review_market_relevant,review_noise_type,review_label_source,review_notes",
                "positive,true,,human_reviewed,keep as relevant",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidReviewDecisionError):
        import_review_decisions_csv(queue_path, csv_path, output_path)


def test_import_review_decisions_csv_rejects_duplicate_sample_ids(tmp_path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    csv_path = tmp_path / "review.csv"
    output_path = tmp_path / "reviewed.jsonl"
    samples = [_sample_payload(sample_id="positive", label_source="model_only")]
    save_samples(queue_path, samples)
    csv_path.write_text(
        "\n".join(
            [
                "sample_id,review_market_relevant,review_noise_type,review_label_source,review_notes",
                "positive,true,,human_reviewed,keep as relevant",
                "positive,false,off_topic,human_corrected,duplicate row",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidReviewDecisionError):
        import_review_decisions_csv(queue_path, csv_path, output_path)


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


def test_sampling_script_includes_article_body_excerpt_when_present(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    module = _load_sampling_module()

    with session_local() as session:
        item = _make_news_item(
            news_id=21,
            source_name="Legacy Feed",
            canonical_url="https://example.com/body-story",
            fetched_at=datetime(2025, 3, 17, 1, 0, tzinfo=timezone.utc),
        )
        session.add(item)
        session.flush()
        session.add(
            ArticleContent(
                news_id=item.id,
                content_text="Body excerpt with revenue guidance and supply chain detail.",
                content_html=None,
                extract_status="success",
                extract_error=None,
                extracted_at=datetime(2025, 3, 17, 1, 5, tzinfo=timezone.utc),
            )
        )
        session.commit()
        monkeypatch.setattr(module, "load_sources", lambda: [])

        records = module.build_market_relevance_candidates(session, historical_limit=1, realtime_limit=0)

    assert records[0].content.body_excerpt == "Body excerpt with revenue guidance and supply chain detail."


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


def test_sampling_script_can_cap_per_source_to_reduce_overrepresentation(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    module = _load_sampling_module()

    with session_local() as session:
        for index in range(1, 6):
            session.add(
                _make_news_item(
                    news_id=index,
                    source_name="CLS Telegraph",
                    canonical_url=f"https://example.com/cls-{index}",
                    fetched_at=datetime(2025, 3, 17, index, 0, tzinfo=timezone.utc),
                )
            )
        session.add(
            _make_news_item(
                news_id=101,
                source_name="Reuters",
                canonical_url="https://example.com/reuters-1",
                fetched_at=datetime(2025, 3, 17, 6, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _make_news_item(
                news_id=102,
                source_name="Bloomberg",
                canonical_url="https://example.com/bloomberg-1",
                fetched_at=datetime(2025, 3, 17, 7, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        monkeypatch.setattr(module, "load_sources", lambda: [])
        records = module.build_market_relevance_candidates(
            session,
            historical_limit=4,
            realtime_limit=0,
            historical_source_cap=1,
        )

    assert [record.origin.source_name for record in records] == [
        "CLS Telegraph",
        "Reuters",
        "Bloomberg",
    ]


def test_sampling_script_source_cap_keeps_filling_beyond_initial_skewed_window(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    module = _load_sampling_module()

    with session_local() as session:
        for index in range(1, 1001):
            session.add(
                _make_news_item(
                    news_id=index,
                    source_name="A",
                    canonical_url=f"https://example.com/a-{index}",
                    fetched_at=datetime(2025, 3, 17, 0, 0, tzinfo=timezone.utc),
                )
            )
        for index in range(1001, 1011):
            session.add(
                _make_news_item(
                    news_id=index,
                    source_name="B",
                    canonical_url=f"https://example.com/b-{index}",
                    fetched_at=datetime(2025, 3, 18, 0, 0, tzinfo=timezone.utc),
                )
            )
        for index in range(1011, 1021):
            session.add(
                _make_news_item(
                    news_id=index,
                    source_name="C",
                    canonical_url=f"https://example.com/c-{index}",
                    fetched_at=datetime(2025, 3, 19, 0, 0, tzinfo=timezone.utc),
                )
            )
        session.commit()

        monkeypatch.setattr(module, "load_sources", lambda: [])
        records = module.build_market_relevance_candidates(
            session,
            historical_limit=30,
            realtime_limit=0,
            historical_source_cap=10,
        )

    assert len(records) == 30
    assert [record.origin.source_name for record in records[:6]] == ["A", "B", "C", "A", "B", "C"]
