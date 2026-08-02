"""SentimentEvalRunRepository 落库/查询测试：批次分组、最近历史、按 dataset_hash 找上一批。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.session import SessionLocal
from app.models.sentiment_eval_run import SentimentEvalRun
from app.repositories.sentiment_eval_run_repository import SentimentEvalRunRepository


def _clear_table() -> None:
    with SessionLocal() as session:
        session.query(SentimentEvalRun).delete()
        session.commit()


def _add_batch(
    repo: SentimentEvalRunRepository,
    *,
    batch_id: str,
    created_at: datetime,
    dataset_hash: str = "hash-a",
    model_names: list[str],
) -> None:
    for idx, model_name in enumerate(model_names):
        repo.add_run(
            batch_id=batch_id,
            created_at=created_at,
            dataset_path="data/research/sentiment_gold_benchmark.json",
            dataset_hash=dataset_hash,
            sample_count=20,
            model_name=model_name,
            config_json=None,
            accuracy=0.5 + idx * 0.01,
            macro_f1=0.5 + idx * 0.01,
            importance_weighted_accuracy=None,
            per_label_json="[]",
            confusion_json="{}",
            note=None,
        )


def test_add_run_persists_row() -> None:
    _clear_table()
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        row = repo.add_run(
            batch_id="batch-1",
            created_at=datetime.now(UTC),
            dataset_path="data/x.json",
            dataset_hash="abc123",
            sample_count=10,
            model_name="rule-baseline",
            config_json='{"positive_threshold": 0.2}',
            accuracy=0.8,
            macro_f1=0.75,
            importance_weighted_accuracy=0.79,
            per_label_json="[]",
            confusion_json="{}",
            note="test note",
        )
        session.commit()
        assert row.id is not None

    with SessionLocal() as session:
        fetched = session.get(SentimentEvalRun, row.id)
        assert fetched is not None
        assert fetched.model_name == "rule-baseline"
        assert fetched.accuracy == 0.8
        assert fetched.importance_weighted_accuracy == 0.79
        assert fetched.note == "test note"


def test_list_recent_batches_groups_by_batch_id_newest_first() -> None:
    _clear_table()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        _add_batch(
            repo,
            batch_id="batch-old",
            created_at=now - timedelta(hours=2),
            model_names=["rule-baseline", "rule-sensitive (±0.10)"],
        )
        _add_batch(
            repo,
            batch_id="batch-new",
            created_at=now,
            model_names=["rule-baseline", "llm:openai/gpt", "hybrid:openai/gpt"],
        )
        session.commit()

        batches = repo.list_recent_batches(limit=20)

    assert [batch[0].batch_id for batch in batches] == ["batch-new", "batch-old"]
    # batch 内部保持插入顺序 (id 升序)
    assert [row.model_name for row in batches[0]] == [
        "rule-baseline",
        "llm:openai/gpt",
        "hybrid:openai/gpt",
    ]


def test_list_recent_batches_respects_limit() -> None:
    _clear_table()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        for i in range(3):
            _add_batch(
                repo,
                batch_id=f"batch-{i}",
                created_at=now - timedelta(hours=i),
                model_names=["rule-baseline"],
            )
        session.commit()

        batches = repo.list_recent_batches(limit=2)

    assert len(batches) == 2
    assert batches[0][0].batch_id == "batch-0"
    assert batches[1][0].batch_id == "batch-1"


def test_get_latest_batch_returns_empty_list_when_no_rows() -> None:
    _clear_table()
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        assert repo.get_latest_batch() == []


def test_get_latest_batch_returns_most_recent() -> None:
    _clear_table()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        _add_batch(repo, batch_id="batch-old", created_at=now - timedelta(hours=1), model_names=["rule-baseline"])
        _add_batch(repo, batch_id="batch-new", created_at=now, model_names=["rule-baseline"])
        session.commit()

        latest = repo.get_latest_batch()

    assert len(latest) == 1
    assert latest[0].batch_id == "batch-new"


def test_get_previous_batch_for_dataset_hash_matches_hash_and_excludes_current() -> None:
    _clear_table()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        _add_batch(
            repo,
            batch_id="batch-a-old",
            created_at=now - timedelta(hours=3),
            dataset_hash="hash-a",
            model_names=["rule-baseline"],
        )
        _add_batch(
            repo,
            batch_id="batch-b",
            created_at=now - timedelta(hours=2),
            dataset_hash="hash-b",
            model_names=["rule-baseline"],
        )
        _add_batch(
            repo,
            batch_id="batch-a-new",
            created_at=now,
            dataset_hash="hash-a",
            model_names=["rule-baseline"],
        )
        session.commit()

        previous = repo.get_previous_batch_for_dataset_hash(
            dataset_hash="hash-a", exclude_batch_id="batch-a-new"
        )

    assert len(previous) == 1
    assert previous[0].batch_id == "batch-a-old"


def test_get_previous_batch_for_dataset_hash_returns_empty_when_no_match() -> None:
    _clear_table()
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        _add_batch(repo, batch_id="batch-1", created_at=datetime.now(UTC), dataset_hash="only-hash", model_names=["rule-baseline"])
        session.commit()

        previous = repo.get_previous_batch_for_dataset_hash(
            dataset_hash="only-hash", exclude_batch_id="batch-1"
        )

    assert previous == []
