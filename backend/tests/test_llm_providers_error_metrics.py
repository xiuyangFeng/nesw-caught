"""Observability tests for optimization-plan.md #12: several `except Exception`
blocks in `app/services/llm_providers.py` are best-effort side channels (token
usage logging, classification cache read/write) that intentionally swallow
failures and keep going. This file verifies the swallowed failures are now
counted instead of only appearing in a log line.
"""

from __future__ import annotations

import pytest

from app.services import llm_providers


def test_log_token_usage_failure_increments_error_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    before = llm_providers.get_llm_provider_error_counts()["token_usage_log_failed"]

    def _boom(**_kwargs: object) -> None:
        raise RuntimeError("buffer exploded")

    monkeypatch.setattr(llm_providers.token_usage_buffer, "add", _boom)

    # Should not raise: a failed token-usage log is a best-effort side channel.
    llm_providers.log_token_usage("model-x", 1, 2, "chat")

    after = llm_providers.get_llm_provider_error_counts()["token_usage_log_failed"]
    assert after == before + 1


def test_classification_cache_read_and_write_failures_increment_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BoomRepo:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get_by_hash(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("cache read exploded")

        def upsert(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("cache write exploded")

    monkeypatch.setattr(
        "app.repositories.llm_classification_cache_repository.LLMClassificationCacheRepository",
        _BoomRepo,
    )

    before = llm_providers.get_llm_provider_error_counts()
    read_before = before["classification_cache_read_failed"]
    write_before = before["classification_cache_write_failed"]

    # Both should degrade gracefully rather than raise.
    assert llm_providers.get_cached_classification("some-hash") is None
    llm_providers.store_classification("some-hash", "{}", "model-x")

    after = llm_providers.get_llm_provider_error_counts()
    assert after["classification_cache_read_failed"] == read_before + 1
    assert after["classification_cache_write_failed"] == write_before + 1
