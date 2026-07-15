"""Direct unit tests for TokenUsageBuffer batching -- previously untestable
because the buffer forced flush_n=1 whenever pytest was running. Batch sizing
is now injected explicitly via constructor arguments (falling back to
Settings.token_usage_flush_n / token_usage_flush_secs)."""

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage
from app.services.token_usage_buffer import TokenUsageBuffer


def _row(model_name: str) -> dict:
    return {
        "model_name": model_name,
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "operation_type": "test",
    }


def _count(model_name: str) -> int:
    with SessionLocal() as session:
        return session.scalar(
            select(func.count())
            .select_from(LLMTokenUsage)
            .where(LLMTokenUsage.model_name == model_name)
        )


@pytest.fixture()
def cleanup_rows():
    names: list[str] = []
    yield names
    with SessionLocal() as session:
        if names:
            session.query(LLMTokenUsage).filter(
                LLMTokenUsage.model_name.in_(names)
            ).delete(synchronize_session=False)
            session.commit()


def test_buffer_holds_rows_until_flush_n_reached(cleanup_rows):
    model = "buffer-batch-model"
    cleanup_rows.append(model)
    buffer = TokenUsageBuffer(flush_n=3, flush_secs=3600.0)

    buffer.add(**_row(model))
    buffer.add(**_row(model))
    # Below the batch threshold: nothing persisted yet
    assert _count(model) == 0
    assert len(buffer._buf) == 2

    buffer.add(**_row(model))
    # Third row reaches flush_n: the whole batch lands in one bulk insert
    assert _count(model) == 3
    assert len(buffer._buf) == 0


def test_explicit_flush_persists_partial_batch(cleanup_rows):
    model = "buffer-partial-model"
    cleanup_rows.append(model)
    buffer = TokenUsageBuffer(flush_n=100, flush_secs=3600.0)

    buffer.add(**_row(model))
    assert _count(model) == 0

    buffer.flush()
    assert _count(model) == 1
    assert len(buffer._buf) == 0

    # Flushing an empty buffer is a no-op
    buffer.flush()
    assert _count(model) == 1


def test_add_flushes_when_flush_secs_elapsed(cleanup_rows):
    model = "buffer-timed-model"
    cleanup_rows.append(model)
    buffer = TokenUsageBuffer(flush_n=100, flush_secs=3600.0)

    buffer.add(**_row(model))
    assert _count(model) == 0

    # Simulate the flush interval having elapsed since the last flush
    buffer._last -= 3601.0
    buffer.add(**_row(model))
    assert _count(model) == 2


def test_flush_n_defaults_to_settings():
    # conftest sets TOKEN_USAGE_FLUSH_N=1 so existing tests keep synchronous
    # persistence semantics without any pytest runtime detection.
    buffer = TokenUsageBuffer()
    assert buffer._flush_n == 1
