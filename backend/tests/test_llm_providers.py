"""Unit tests for the shared helpers extracted in the llm_providers refactor."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_providers import (
    AsyncOpenAICompatibleProvider,
    CompletionResult,
    LLMProviderError,
    OpenAICompatibleProvider,
    parse_chat_completion,
    parse_embedding_response,
    plan_failover,
    raise_provider_error,
    resolve_completion_usage,
    validate_provider_config,
)


def _config(**overrides) -> SimpleNamespace:
    base = dict(
        id=1,
        base_url="https://api.primary.com/v1",
        model_name="primary-model",
        decrypted_api_key="sk-primary",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# parse_chat_completion
# ---------------------------------------------------------------------------

def test_parse_chat_completion_returns_content_and_usage() -> None:
    payload = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5},
    }
    content, usage = parse_chat_completion(payload)
    assert content == "Hello"
    assert usage == {"prompt_tokens": 3, "completion_tokens": 5}


def test_parse_chat_completion_without_usage_returns_none() -> None:
    content, usage = parse_chat_completion({"choices": [{"message": {"content": "Hi"}}]})
    assert content == "Hi"
    assert usage is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"choices": []},
        {"choices": "not-a-list"},
        {"choices": [{"message": None}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "   "}}]},
    ],
)
def test_parse_chat_completion_rejects_malformed_payloads(payload) -> None:
    with pytest.raises(LLMProviderError):
        parse_chat_completion(payload)


# ---------------------------------------------------------------------------
# parse_embedding_response
# ---------------------------------------------------------------------------

def test_parse_embedding_response_returns_vector_and_usage() -> None:
    payload = {
        "data": [{"embedding": [1, 2.5]}],
        "usage": {"prompt_tokens": 7},
    }
    vector, usage = parse_embedding_response(payload)
    assert vector == [1.0, 2.5]
    assert usage == {"prompt_tokens": 7}


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"data": []}, {"data": [{"embedding": []}]}, {"data": [{}]}],
)
def test_parse_embedding_response_rejects_malformed_payloads(payload) -> None:
    with pytest.raises(LLMProviderError):
        parse_embedding_response(payload)


# ---------------------------------------------------------------------------
# resolve_completion_usage
# ---------------------------------------------------------------------------

def test_resolve_completion_usage_prefers_reported_usage() -> None:
    usage = {"prompt_tokens": 11, "completion_tokens": 22}
    assert resolve_completion_usage(usage, [], "anything") == (11, 22)


def test_resolve_completion_usage_estimates_when_usage_missing() -> None:
    messages = [{"role": "user", "content": "x" * 40}]
    prompt_tokens, completion_tokens = resolve_completion_usage(None, messages, "y" * 8)
    assert prompt_tokens == 10  # 40 chars / 4
    assert completion_tokens == 2  # 8 chars / 4


# ---------------------------------------------------------------------------
# validate_provider_config
# ---------------------------------------------------------------------------

def test_validate_provider_config_accepts_real_looking_config() -> None:
    validate_provider_config(_config())  # should not raise


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"base_url": ""}, "not configured"),
        ({"base_url": None}, "not configured"),
        ({"base_url": "https://example.com/v1"}, "placeholder base url"),
        ({"base_url": "https://api.foo.test/v1"}, "placeholder base url"),
        ({"decrypted_api_key": "sk-test-123"}, "placeholder api key"),
    ],
)
def test_validate_provider_config_rejects_placeholders(overrides, match) -> None:
    with pytest.raises(LLMProviderError, match=match):
        validate_provider_config(_config(**overrides))


# ---------------------------------------------------------------------------
# plan_failover / raise_provider_error
# ---------------------------------------------------------------------------

def test_plan_failover_returns_backup_and_info() -> None:
    backup = _config(id=2, model_name="backup-model")
    with patch("app.services.llm_providers.find_backup_config", return_value=backup) as mock_find:
        backup_config, info = plan_failover(_config(), RuntimeError("boom"), 0, "Test op")

    mock_find.assert_called_once_with(1)
    assert backup_config is backup
    assert info == {"from_model": "primary-model", "to_model": "backup-model", "reason": "boom"}


def test_plan_failover_stops_after_one_retry() -> None:
    with patch("app.services.llm_providers.find_backup_config") as mock_find:
        assert plan_failover(_config(), RuntimeError("boom"), 1, "Test op") == (None, None)
    mock_find.assert_not_called()


def test_plan_failover_without_backup_returns_none() -> None:
    with patch("app.services.llm_providers.find_backup_config", return_value=None):
        assert plan_failover(_config(), RuntimeError("boom"), 0, "Test op") == (None, None)


def test_raise_provider_error_reraises_provider_error_as_is() -> None:
    original = LLMProviderError("original")
    with pytest.raises(LLMProviderError) as exc_info:
        raise_provider_error(original, "prefix")
    assert exc_info.value is original


def test_raise_provider_error_wraps_other_exceptions() -> None:
    original = ValueError("bad")
    with pytest.raises(LLMProviderError, match="prefix: bad") as exc_info:
        raise_provider_error(original, "prefix")
    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# provider-level behavior
# ---------------------------------------------------------------------------

def test_sync_complete_raises_without_backup() -> None:
    provider = OpenAICompatibleProvider(_config(base_url="https://example.com/v1"))
    with patch("app.services.llm_providers.find_backup_config", return_value=None):
        with pytest.raises(LLMProviderError, match="placeholder base url"):
            provider.complete(messages=[{"role": "user", "content": "ping"}])
    assert provider.failover_triggered is None


def test_async_complete_fails_over_to_backup() -> None:
    primary = _config(base_url="https://example.com/v1")  # placeholder → fails validation
    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = {
        "choices": [{"message": {"content": "Backup wins"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=ok_response)

    provider = AsyncOpenAICompatibleProvider(primary)
    with patch("app.services.llm_providers.find_backup_config", return_value=backup), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client):
        result = asyncio.run(provider.complete(messages=[{"role": "user", "content": "ping"}]))

    assert isinstance(result, CompletionResult)
    assert result.content == "Backup wins"
    assert result.failover == {
        "from_model": "primary-model",
        "to_model": "backup-model",
        "reason": "llm provider uses placeholder base url: https://example.com/v1",
    }
    assert provider.failover_triggered == result.failover


def test_chat_stream_yields_typed_failover_and_token_events() -> None:
    primary = _config(base_url="https://example.com/v1")  # placeholder → fails validation
    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    class FakeStreamResponse:
        status_code = 200

        async def aread(self) -> bytes:
            return b""

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Hi"}}]}'
            yield 'data: {"usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": []}'
            yield "data: [DONE]"

    class FakeAsyncClient:
        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            yield FakeStreamResponse()

    provider = AsyncOpenAICompatibleProvider(primary)

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "ping"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers.find_backup_config", return_value=backup), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=FakeAsyncClient()):
        events = asyncio.run(_collect())

    assert events[0][0] == "failover"
    assert events[0][1]["from_model"] == "primary-model"
    assert events[0][1]["to_model"] == "backup-model"
    assert events[1] == ("token", "Hi")


# ---------------------------------------------------------------------------
# http_pool async client
# ---------------------------------------------------------------------------

def test_get_async_llm_client_is_singleton_and_closable() -> None:
    from app.services import http_pool

    async def _run() -> None:
        first = http_pool.get_async_llm_client()
        second = http_pool.get_async_llm_client()
        assert first is second
        await http_pool.aclose_async_llm_client()
        assert http_pool._async_client is None
        third = http_pool.get_async_llm_client()
        assert third is not first
        await http_pool.aclose_async_llm_client()

    asyncio.run(_run())
