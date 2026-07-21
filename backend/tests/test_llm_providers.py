"""Unit tests for the shared helpers extracted in the llm_providers refactor."""

import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.llm_providers import (
    AsyncOpenAICompatibleProvider,
    CompletionResult,
    LLMProviderError,
    OpenAICompatibleProvider,
    compute_backoff_delay,
    is_retryable_error,
    parse_chat_completion,
    parse_embedding_response,
    parse_embeddings_response,
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
# parse_embeddings_response (Task 7: batch embed_texts)
# ---------------------------------------------------------------------------

def test_parse_embeddings_response_returns_vectors_in_index_order() -> None:
    payload = {
        "data": [
            {"index": 1, "embedding": [2, 2]},
            {"index": 0, "embedding": [1, 1]},
        ],
        "usage": {"prompt_tokens": 9},
    }
    vectors, usage = parse_embeddings_response(payload, expected_count=2)
    assert vectors == [[1.0, 1.0], [2.0, 2.0]]
    assert usage == {"prompt_tokens": 9}


def test_parse_embeddings_response_defaults_to_position_when_index_missing() -> None:
    payload = {"data": [{"embedding": [1, 1]}, {"embedding": [2, 2]}]}
    vectors, _ = parse_embeddings_response(payload, expected_count=2)
    assert vectors == [[1.0, 1.0], [2.0, 2.0]]


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"data": []}, {"data": [{"embedding": []}]}, {"data": [{}]}],
)
def test_parse_embeddings_response_rejects_malformed_payloads(payload) -> None:
    with pytest.raises(LLMProviderError):
        parse_embeddings_response(payload, expected_count=1)


def test_parse_embeddings_response_rejects_count_mismatch() -> None:
    payload = {"data": [{"index": 0, "embedding": [1, 1]}]}
    with pytest.raises(LLMProviderError, match="expected 2"):
        parse_embeddings_response(payload, expected_count=2)


def test_parse_embeddings_response_rejects_duplicate_indices() -> None:
    """终审发现：只校验 count 相等，未校验 index 集合本身——provider 返回重复
    index（如两条都标 index=0，缺 index=1）时，count 恰好还是对的，排序后会
    把错误的向量悄悄放到某个位置，下游（如个股研判排序）拿到的是错位的
    embedding，且不会抛异常。这里要求 index 集合必须恰好等于 0..N-1。"""
    payload = {
        "data": [
            {"index": 0, "embedding": [1, 1]},
            {"index": 0, "embedding": [9, 9]},
            {"index": 2, "embedding": [3, 3]},
        ],
    }
    with pytest.raises(LLMProviderError, match="unexpected indices"):
        parse_embeddings_response(payload, expected_count=3)


# ---------------------------------------------------------------------------
# is_retryable_error / compute_backoff_delay
# ---------------------------------------------------------------------------

def test_is_retryable_error_classifies_by_status_and_transport_type() -> None:
    assert is_retryable_error(LLMProviderError("x", status_code=429, retryable=True)) is True
    assert is_retryable_error(LLMProviderError("x", status_code=500, retryable=True)) is True
    assert is_retryable_error(LLMProviderError("x", status_code=400, retryable=False)) is False
    assert is_retryable_error(LLMProviderError("x")) is False  # 默认不可重试
    assert is_retryable_error(
        httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://api.example.com"))
    ) is True
    assert is_retryable_error(ValueError("not an llm/http error")) is False


def test_compute_backoff_delay_is_exponential_with_bounded_jitter() -> None:
    delay_0 = compute_backoff_delay(0.5, 0)
    delay_1 = compute_backoff_delay(0.5, 1)
    assert 0.5 <= delay_0 < 0.5 * 1.25
    assert 1.0 <= delay_1 < 1.0 * 1.25


# ---------------------------------------------------------------------------
# embed_texts (Task 7: batch embedding)
# ---------------------------------------------------------------------------

def _sync_response(status_code: int, payload: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_embed_texts_sends_single_batched_request_and_aligns_by_index() -> None:
    """query+全部文档合并为一次请求；响应乱序返回时按 index 对齐，而非按数组顺序。"""
    captured_bodies: list[dict] = []

    def fake_post(url, headers=None, json=None):
        captured_bodies.append(json)
        return _sync_response(
            200,
            {
                "data": [
                    {"index": 1, "embedding": [2.0, 2.0]},
                    {"index": 0, "embedding": [1.0, 1.0]},
                ],
                "usage": {"prompt_tokens": 9},
            },
        )

    fake_client = MagicMock()
    fake_client.post.side_effect = fake_post

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.log_token_usage") as mock_log:
        vectors = provider.embed_texts(["doc-a", "doc-b"])

    assert fake_client.post.call_count == 1
    assert captured_bodies[0]["input"] == ["doc-a", "doc-b"]
    # 对齐到响应声明的 index，而不是数组的原始（乱序）顺序。
    assert vectors == [[1.0, 1.0], [2.0, 2.0]]
    mock_log.assert_called_once_with(
        model_name="primary-model", prompt_tokens=9, completion_tokens=0, operation_type="embedding"
    )


def test_embed_texts_empty_list_returns_empty_without_request() -> None:
    fake_client = MagicMock()
    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client):
        assert provider.embed_texts([]) == []
    fake_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# same-provider retry before failover (Task 7)
# ---------------------------------------------------------------------------

def test_sync_complete_retries_on_429_then_succeeds_without_failover(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: sleeps.append(s))

    fake_client = MagicMock()
    fake_client.post.side_effect = [
        _sync_response(429, {"error": {"message": "rate limited"}}),
        _sync_response(
            200,
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        ),
    ]

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config") as mock_find:
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert fake_client.post.call_count == 2
    assert len(sleeps) == 1  # 恰好重试一次后成功，不应触发 failover 查找
    mock_find.assert_not_called()
    assert provider.failover_triggered is None


def test_sync_complete_retries_on_timeout_then_succeeds(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: sleeps.append(s))

    timeout_exc = httpx.ReadTimeout(
        "timed out", request=httpx.Request("POST", "https://api.primary.com/v1/chat/completions")
    )
    fake_client = MagicMock()
    fake_client.post.side_effect = [
        timeout_exc,
        _sync_response(
            200,
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        ),
    ]

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config") as mock_find:
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert fake_client.post.call_count == 2
    assert len(sleeps) == 1
    mock_find.assert_not_called()


def test_sync_complete_does_not_retry_on_400(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: sleeps.append(s))

    fake_client = MagicMock()
    fake_client.post.return_value = _sync_response(400, {"error": {"message": "bad request"}})

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=None):
        with pytest.raises(LLMProviderError, match="bad request"):
            provider.complete(messages=[{"role": "user", "content": "hi"}])

    # 除 429 外的 4xx 不重试：只应打一次，直接判定 failover(无 backup 则上抛)。
    assert fake_client.post.call_count == 1
    assert sleeps == []


def test_sync_complete_retry_exhausted_then_fails_over(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: sleeps.append(s))

    backup = _config(
        id=2, model_name="backup-model", base_url="https://api.backup.com/v1", decrypted_api_key="sk-backup"
    )
    call_urls: list[str] = []

    def fake_post(url, headers=None, json=None):
        call_urls.append(url)
        if url.startswith("https://api.primary.com"):
            return _sync_response(500, {"error": {"message": "server error"}})
        return _sync_response(
            200,
            {
                "choices": [{"message": {"content": "from backup"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    fake_client = MagicMock()
    fake_client.post.side_effect = fake_post

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "from backup"
    # 默认 llm_retry_max_attempts=2：初始 1 次 + 2 次重试 = 3 次打到 primary，随后 1 次打到 backup。
    assert call_urls.count("https://api.primary.com/v1/chat/completions") == 3
    assert call_urls.count("https://api.backup.com/v1/chat/completions") == 1
    assert len(sleeps) == 2
    assert provider.failover_triggered is not None


# ---------------------------------------------------------------------------
# backup provider must not get the full retry budget after failover
# (Task 7 修复轮 #1)：backup 只做单次尝试，不复用 llm_retry_max_attempts 那一整套
# 同 provider 重试预算——否则最坏情况下 primary 打满重试 + backup 又打满重试，
# 挂起时长可能翻倍甚至达到分钟级。
# ---------------------------------------------------------------------------

def test_sync_complete_backup_provider_does_not_get_full_retry_budget(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: sleeps.append(s))

    backup = _config(
        id=2, model_name="backup-model", base_url="https://api.backup.com/v1", decrypted_api_key="sk-backup"
    )
    call_urls: list[str] = []

    def fake_post(url, headers=None, json=None):
        call_urls.append(url)
        # primary 和 backup 都持续返回可重试的 5xx。
        return _sync_response(500, {"error": {"message": "server error"}})

    fake_client = MagicMock()
    fake_client.post.side_effect = fake_post

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        with pytest.raises(LLMProviderError, match="server error"):
            provider.complete(messages=[{"role": "user", "content": "hi"}])

    # 默认 llm_retry_max_attempts=2：primary 打满 1 初始 + 2 重试 = 3 次后 failover；
    # backup 遇到同样可重试的错误也应该只尝试 1 次就放弃，不再重复走一整套重试预算。
    assert call_urls.count("https://api.primary.com/v1/chat/completions") == 3
    assert call_urls.count("https://api.backup.com/v1/chat/completions") == 1
    assert len(sleeps) == 2  # 只有 primary 的两次重试触发了退避 sleep，backup 没有
    assert provider.failover_triggered is not None


def test_sync_embed_text_backup_provider_does_not_get_full_retry_budget(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: None)

    backup = _config(
        id=2, model_name="backup-model", base_url="https://api.backup.com/v1", decrypted_api_key="sk-backup"
    )
    call_urls: list[str] = []

    def fake_post(url, headers=None, json=None):
        call_urls.append(url)
        return _sync_response(500, {"error": {"message": "server error"}})

    fake_client = MagicMock()
    fake_client.post.side_effect = fake_post

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        with pytest.raises(LLMProviderError, match="server error"):
            provider.embed_text("hello")

    assert call_urls.count("https://api.primary.com/v1/embeddings") == 3
    assert call_urls.count("https://api.backup.com/v1/embeddings") == 1


def test_sync_embed_texts_backup_provider_does_not_get_full_retry_budget(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_providers._retry_sleep", lambda s: None)

    backup = _config(
        id=2, model_name="backup-model", base_url="https://api.backup.com/v1", decrypted_api_key="sk-backup"
    )
    call_urls: list[str] = []

    def fake_post(url, headers=None, json=None):
        call_urls.append(url)
        return _sync_response(500, {"error": {"message": "server error"}})

    fake_client = MagicMock()
    fake_client.post.side_effect = fake_post

    provider = OpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        with pytest.raises(LLMProviderError, match="server error"):
            provider.embed_texts(["doc-a", "doc-b"])

    assert call_urls.count("https://api.primary.com/v1/embeddings") == 3
    assert call_urls.count("https://api.backup.com/v1/embeddings") == 1


# ---------------------------------------------------------------------------
# async provider: retry + off-event-loop DB calls (Task 7 补充要求)
# ---------------------------------------------------------------------------

def test_async_complete_retries_on_5xx_then_succeeds_without_failover() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        side_effect=[
            _sync_response(503, {"error": {"message": "unavailable"}}),
            _sync_response(
                200,
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            ),
        ]
    )

    provider = AsyncOpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers._retry_sleep_async", fake_sleep), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config") as mock_find:
        result = asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}]))

    assert result.content == "ok"
    assert fake_client.post.await_count == 2
    assert len(sleeps) == 1
    mock_find.assert_not_called()


def test_async_complete_runs_failover_lookup_off_event_loop_thread() -> None:
    """补充要求：AsyncOpenAICompatibleProvider.complete() 里 plan_failover(内部同步读 DB
    的 find_backup_config) 不能占用事件循环线程。"""
    main_thread_id = threading.get_ident()
    call_thread_ids: list[int] = []

    primary = _config(base_url="https://example.com/v1")  # placeholder → 校验失败,不可重试,直接判定 failover
    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    def _find_backup(exclude_id):
        call_thread_ids.append(threading.get_ident())
        return backup

    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        return_value=_sync_response(
            200,
            {
                "choices": [{"message": {"content": "from backup"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )

    provider = AsyncOpenAICompatibleProvider(primary)
    with patch("app.services.llm_providers.find_backup_config", side_effect=_find_backup), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client):
        result = asyncio.run(provider.complete(messages=[{"role": "user", "content": "ping"}]))

    assert result.content == "from backup"
    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id


def test_async_complete_runs_token_usage_logging_off_event_loop_thread() -> None:
    """补充要求：log_token_usage -> TokenUsageBuffer.add() 的同步写不能占用事件循环线程。"""
    main_thread_id = threading.get_ident()
    call_thread_ids: list[int] = []

    def _fake_add(**_row: object) -> None:
        call_thread_ids.append(threading.get_ident())

    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        return_value=_sync_response(
            200,
            {
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        )
    )

    provider = AsyncOpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.token_usage_buffer.add", side_effect=_fake_add):
        asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}]))

    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id


def test_async_complete_backup_provider_does_not_get_full_retry_budget() -> None:
    """Task 7 修复轮 #1（async 路径）：primary 重试耗尽 failover 后，backup 遇到同样
    可重试的错误也应该只尝试 1 次就放弃，不复用整套 llm_retry_max_attempts 预算。"""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    backup = _config(
        id=2, model_name="backup-model", base_url="https://api.backup.com/v1", decrypted_api_key="sk-backup"
    )
    call_urls: list[str] = []

    async def fake_post(url, headers=None, json=None):
        call_urls.append(url)
        return _sync_response(500, {"error": {"message": "server error"}})

    fake_client = MagicMock()
    fake_client.post = AsyncMock(side_effect=fake_post)

    provider = AsyncOpenAICompatibleProvider(_config())
    with patch("app.services.llm_providers._retry_sleep_async", fake_sleep), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        with pytest.raises(LLMProviderError, match="server error"):
            asyncio.run(provider.complete(messages=[{"role": "user", "content": "hi"}]))

    assert call_urls.count("https://api.primary.com/v1/chat/completions") == 3
    assert call_urls.count("https://api.backup.com/v1/chat/completions") == 1
    assert len(sleeps) == 2


# ---------------------------------------------------------------------------
# chat_stream: retry only allowed before the first byte (Task 7)
# ---------------------------------------------------------------------------

def test_chat_stream_retries_before_first_byte_then_succeeds_without_failover() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    class FailStreamResponse:
        status_code = 503

        async def aread(self) -> bytes:
            return b""

        def json(self) -> dict:
            return {"error": {"message": "service unavailable"}}

    class OkStreamResponse:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Hi"}}]}'
            yield 'data: {"usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": []}'
            yield "data: [DONE]"

    attempts = {"n": 0}

    class FakeAsyncClient:
        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                yield FailStreamResponse()
            else:
                yield OkStreamResponse()

    provider = AsyncOpenAICompatibleProvider(_config())

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "ping"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers._retry_sleep_async", fake_sleep), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=FakeAsyncClient()), \
         patch("app.services.llm_providers.find_backup_config") as mock_find:
        events = asyncio.run(_collect())

    assert events == [("token", "Hi")]
    assert attempts["n"] == 2
    assert len(sleeps) == 1
    mock_find.assert_not_called()


def test_chat_stream_does_not_retry_after_first_byte_goes_straight_to_failover() -> None:
    """流已经吐出至少一个 token 后中断：不重试同一 provider，直接按既有语义判定 failover。"""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    class InterruptedStreamResponse:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Hi"}}]}'
            raise httpx.ReadError(
                "connection reset",
                request=httpx.Request("POST", "https://api.primary.com/v1/chat/completions"),
            )

    class BackupStreamResponse:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Backup"}}]}'
            yield "data: [DONE]"

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.calls = 0

        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            self.calls += 1
            if "primary" in url:
                yield InterruptedStreamResponse()
            else:
                yield BackupStreamResponse()

    fake_client = FakeAsyncClient()
    provider = AsyncOpenAICompatibleProvider(_config())

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "ping"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers._retry_sleep_async", fake_sleep), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        events = asyncio.run(_collect())

    assert events[0] == ("token", "Hi")
    assert events[1][0] == "failover"
    assert events[2] == ("token", "Backup")
    # primary 只被打了一次（收到过 token 之后中断，不重试，直接判定 failover）。
    assert fake_client.calls == 2
    assert sleeps == []


def test_chat_stream_backup_provider_does_not_get_full_retry_budget() -> None:
    """Task 7 修复轮 #1（chat_stream 路径）：primary 首字节前重试耗尽 failover 后，
    backup 遇到同样可重试的错误也应该只尝试 1 次就放弃，不复用整套重试预算。"""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    class FailStreamResponse:
        status_code = 503

        async def aread(self) -> bytes:
            return b""

        def json(self) -> dict:
            return {"error": {"message": "service unavailable"}}

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.call_urls: list[str] = []

        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            self.call_urls.append(url)
            yield FailStreamResponse()

    fake_client = FakeAsyncClient()
    provider = AsyncOpenAICompatibleProvider(_config())

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "ping"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers._retry_sleep_async", fake_sleep), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=fake_client), \
         patch("app.services.llm_providers.find_backup_config", return_value=backup):
        with pytest.raises(LLMProviderError, match="service unavailable"):
            asyncio.run(_collect())

    # 默认 llm_retry_max_attempts=2：primary 打满 1 初始 + 2 重试 = 3 次后 failover；
    # backup 遇到同样可重试的错误只应尝试 1 次。
    assert fake_client.call_urls.count("https://api.primary.com/v1/chat/completions") == 3
    assert fake_client.call_urls.count("https://api.backup.com/v1/chat/completions") == 1
    assert len(sleeps) == 2


# ---------------------------------------------------------------------------
# chat_stream: plan_failover / log_token_usage must not block the event loop
# thread (Task 7 修复轮 #2 —— 与 test_async_complete_runs_*_off_event_loop_thread
# 对应的 chat_stream 版本)
# ---------------------------------------------------------------------------

def test_chat_stream_runs_failover_lookup_off_event_loop_thread() -> None:
    """chat_stream() 里 plan_failover(内部同步读 DB 的 find_backup_config) 不能占用
    事件循环线程。"""
    main_thread_id = threading.get_ident()
    call_thread_ids: list[int] = []

    primary = _config(base_url="https://example.com/v1")  # placeholder → 校验失败,不可重试,直接判定 failover
    backup = _config(id=2, model_name="backup-model", base_url="https://api.backup.com/v1",
                     decrypted_api_key="sk-backup")

    def _find_backup(exclude_id):
        call_thread_ids.append(threading.get_ident())
        return backup

    class BackupStreamResponse:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Backup"}}]}'
            yield "data: [DONE]"

    class FakeAsyncClient:
        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            yield BackupStreamResponse()

    provider = AsyncOpenAICompatibleProvider(primary)

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "ping"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers.find_backup_config", side_effect=_find_backup), \
         patch("app.services.llm_providers.get_async_llm_client", return_value=FakeAsyncClient()):
        events = asyncio.run(_collect())

    assert events[0][0] == "failover"
    assert events[1] == ("token", "Backup")
    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id


def test_chat_stream_runs_token_usage_logging_off_event_loop_thread() -> None:
    """chat_stream() 成功收尾时的 log_token_usage -> TokenUsageBuffer.add() 同步写
    不能占用事件循环线程。"""
    main_thread_id = threading.get_ident()
    call_thread_ids: list[int] = []

    def _fake_add(**_row: object) -> None:
        call_thread_ids.append(threading.get_ident())

    class OkStreamResponse:
        status_code = 200

        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": "Hi"}}]}'
            yield 'data: {"usage": {"prompt_tokens": 1, "completion_tokens": 1}, "choices": []}'
            yield "data: [DONE]"

    class FakeAsyncClient:
        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            yield OkStreamResponse()

    provider = AsyncOpenAICompatibleProvider(_config())

    async def _collect() -> list:
        events = []
        async for event in provider.chat_stream(messages=[{"role": "user", "content": "hi"}]):
            events.append(event)
        return events

    with patch("app.services.llm_providers.get_async_llm_client", return_value=FakeAsyncClient()), \
         patch("app.services.llm_providers.token_usage_buffer.add", side_effect=_fake_add):
        events = asyncio.run(_collect())

    assert events == [("token", "Hi")]
    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id


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
