from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
import json
import logging
from typing import NoReturn
from urllib.parse import urlparse

import httpx
from app.services.http_pool import get_async_llm_client, get_llm_client

from app.models.llm_provider_config import LLMProviderConfig
from app.db.session import SessionLocal
from app.services.token_usage_buffer import token_usage_buffer

logger = logging.getLogger(__name__)

# Stream event types yielded by AsyncOpenAICompatibleProvider.chat_stream.
STREAM_EVENT_TOKEN = "token"
STREAM_EVENT_FAILOVER = "failover"

# ("token", str) | ("failover", dict[str, str])
StreamEvent = tuple[str, "str | dict[str, str]"]


class LLMProviderError(RuntimeError):
    pass


@dataclass
class CompletionResult:
    """Structured result of a (non-streaming) chat completion."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failover: dict[str, str] | None = None


def find_backup_config(exclude_id: int) -> LLMProviderConfig | None:
    from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
    with SessionLocal() as session:
        return LLMProviderConfigRepository(session).get_backup(exclude_id)


def log_token_usage(model_name: str, prompt_tokens: int, completion_tokens: int, operation_type: str) -> None:
    try:
        token_usage_buffer.add(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            operation_type=operation_type,
        )
    except Exception as exc:
        logger.warning(f"Failed to log token usage to DB: {exc}")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Estimate roughly 1 token per 4 chars for English/Chinese blend
    return max(1, len(text) // 4)


def validate_provider_config(config: LLMProviderConfig) -> None:
    """Reject obviously misconfigured providers (placeholder urls/keys)."""
    base_url = (config.base_url or "").strip()
    if not base_url:
        raise LLMProviderError("llm provider base url is not configured")

    hostname = (urlparse(base_url).hostname or "").lower()
    if hostname.endswith(".test") or hostname in {"example.com", "example.org", "example.net"}:
        raise LLMProviderError(f"llm provider uses placeholder base url: {base_url}")

    api_key = config.decrypted_api_key or ""
    if api_key.startswith("sk-test"):
        raise LLMProviderError("llm provider uses placeholder api key")


def decode_json_response(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise LLMProviderError("llm provider returned invalid json") from exc


def parse_chat_completion(payload: object) -> tuple[str, dict[str, object] | None]:
    """Parse an OpenAI-compatible chat completion payload.

    Returns (content, usage) where usage is the raw usage dict if present.
    Raises LLMProviderError on malformed/empty payloads.
    """
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise LLMProviderError("llm provider returned no choices")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError("llm provider returned empty content")

    usage = payload.get("usage") if isinstance(payload, dict) else None
    return content, usage if isinstance(usage, dict) else None


def parse_embedding_response(payload: object) -> tuple[list[float], dict[str, object] | None]:
    """Parse an OpenAI-compatible embeddings payload into (vector, usage)."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise LLMProviderError("llm provider returned no embeddings")

    embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
    if not isinstance(embedding, list) or not embedding:
        raise LLMProviderError("llm provider returned empty embedding")

    usage = payload.get("usage") if isinstance(payload, dict) else None
    return [float(value) for value in embedding], usage if isinstance(usage, dict) else None


def resolve_completion_usage(
    usage: dict[str, object] | None,
    messages: list[dict[str, str]],
    content: str,
) -> tuple[int, int]:
    """Resolve (prompt_tokens, completion_tokens), estimating when usage is absent."""
    if isinstance(usage, dict):
        return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    prompt_text = "".join(m.get("content", "") for m in messages)
    return estimate_tokens(prompt_text), estimate_tokens(content)


def plan_failover(
    config: LLMProviderConfig,
    exc: Exception,
    retry_count: int,
    context: str,
) -> tuple[LLMProviderConfig | None, dict[str, str] | None]:
    """Decide whether a failover retry should happen after ``exc``.

    Returns (backup_config, failover_info); (None, None) means no retry
    (either retries are exhausted or no backup provider is configured).
    The single-retry semantics of provider failover live here.
    """
    if retry_count >= 1:
        return None, None
    backup_config = find_backup_config(getattr(config, "id", 0))
    if backup_config is None:
        return None, None
    failover_info = {
        "from_model": config.model_name,
        "to_model": backup_config.model_name,
        "reason": str(exc),
    }
    logger.warning(
        f"{context} failed on provider {config.model_name}: {exc}. "
        f"Retrying with backup provider: {backup_config.model_name}."
    )
    return backup_config, failover_info


def raise_provider_error(exc: Exception, prefix: str) -> NoReturn:
    """Re-raise ``exc`` as-is if it already is an LLMProviderError, else wrap it."""
    if isinstance(exc, LLMProviderError):
        raise exc
    raise LLMProviderError(f"{prefix}: {exc}") from exc


class _BaseOpenAICompatibleProvider:
    """Shared config validation, request preparation and response handling.

    Subclasses only implement the transport layer (sync vs async httpx).
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.failover_triggered: dict[str, str] | None = None

    def _validate_config(self) -> None:
        validate_provider_config(self.config)

    def _prepare_request(self) -> tuple[str, dict[str, str]]:
        """Validate config and return (base_url, auth headers)."""
        self._validate_config()
        base_url = (self.config.base_url or "").rstrip("/")
        api_key = self.config.decrypted_api_key
        if not api_key:
            raise LLMProviderError("llm provider api key is not configured")
        return base_url, {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _chat_request_body(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return {
            "model": self.config.model_name,
            "messages": messages,
            **({"response_format": response_format} if response_format else {}),
        }

    def _handle_completion_response(
        self,
        response: httpx.Response,
        messages: list[dict[str, str]],
        operation_type: str,
    ) -> CompletionResult:
        if response.status_code >= 400:
            raise LLMProviderError(self._build_error_message(response))

        payload = decode_json_response(response)
        content, usage = parse_chat_completion(payload)
        prompt_tokens, completion_tokens = resolve_completion_usage(usage, messages, content)

        log_token_usage(
            model_name=self.config.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            operation_type=operation_type,
        )
        return CompletionResult(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    @staticmethod
    def _build_error_message(response: httpx.Response) -> str:
        detail: str | None = None
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    detail = message.strip()
            if detail is None:
                message = payload.get("message")
                if isinstance(message, str) and message.strip():
                    detail = message.strip()

        if detail:
            return f"llm provider request failed: {detail}"
        return f"llm provider request failed with status {response.status_code}"


class OpenAICompatibleProvider(_BaseOpenAICompatibleProvider):
    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> CompletionResult:
        try:
            base_url, headers = self._prepare_request()
            client = get_llm_client()
            try:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=self._chat_request_body(messages, response_format),
                )
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            return self._handle_completion_response(response, messages, operation_type)

        except (LLMProviderError, httpx.HTTPError) as exc:
            backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Chat completion")
            if backup_config is None:
                raise_provider_error(exc, "llm provider request failed")
            self.failover_triggered = failover_info
            result = OpenAICompatibleProvider(backup_config).complete(
                messages=messages,
                response_format=response_format,
                operation_type=operation_type,
                _retry_count=_retry_count + 1,
            )
            result.failover = failover_info
            return result

    def embed_text(self, text: str, _retry_count: int = 0) -> list[float]:
        try:
            base_url, headers = self._prepare_request()
            client = get_llm_client()
            try:
                response = client.post(
                    f"{base_url}/embeddings",
                    headers=headers,
                    json={"model": self.config.model_name, "input": text},
                )
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            if response.status_code >= 400:
                raise LLMProviderError(self._build_error_message(response))

            payload = decode_json_response(response)
            embedding, usage = parse_embedding_response(payload)

            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens", 0)
            else:
                prompt_tokens = estimate_tokens(text)

            log_token_usage(
                model_name=self.config.model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                operation_type="embedding",
            )
            return embedding

        except (LLMProviderError, httpx.HTTPError) as exc:
            backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Embedding")
            if backup_config is None:
                raise_provider_error(exc, "llm provider request failed")
            self.failover_triggered = failover_info
            return OpenAICompatibleProvider(backup_config).embed_text(text, _retry_count=_retry_count + 1)

    def analyze_json(self, *, prompt: str) -> dict[str, object] | object:
        result = self.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze a single news item for stock read-throughs. "
                        "Return JSON only with keys: top_pick, candidates, summary, risk_notes, sentiment, context_limitations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            operation_type="analysis",
        )

        try:
            return json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("llm provider returned invalid analysis payload") from exc

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return self.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            operation_type="translate",
        ).content

    def test_connection(self) -> None:
        self.generate_text(
            system_prompt=(
                "This is a connection test. Reply with a very short plain text response. "
                "Do not use markdown, JSON, or extra explanation."
            ),
            user_prompt="ping",
        )


class AsyncOpenAICompatibleProvider(_BaseOpenAICompatibleProvider):
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> CompletionResult:
        try:
            base_url, headers = self._prepare_request()
            client = get_async_llm_client()
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=self._chat_request_body(messages, response_format),
                )
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            return self._handle_completion_response(response, messages, operation_type)

        except (LLMProviderError, httpx.HTTPError) as exc:
            backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Async chat completion")
            if backup_config is None:
                raise_provider_error(exc, "llm provider request failed")
            self.failover_triggered = failover_info
            result = await AsyncOpenAICompatibleProvider(backup_config).complete(
                messages=messages,
                response_format=response_format,
                operation_type=operation_type,
                _retry_count=_retry_count + 1,
            )
            result.failover = failover_info
            return result

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        result = await self.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            operation_type="translate",
        )
        return result.content

    async def test_connection(self) -> None:
        await self.generate_text(
            system_prompt=(
                "This is a connection test. Reply with a very short plain text response. "
                "Do not use markdown, JSON, or extra explanation."
            ),
            user_prompt="ping",
        )

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream a chat completion as typed events.

        Yields ("token", text_chunk) for content deltas and, when the primary
        provider fails and a backup takes over, a single ("failover", info)
        event before the backup stream starts.
        """
        try:
            base_url, headers = self._prepare_request()

            accumulated_tokens_text: list[str] = []
            prompt_tokens_from_options = None
            completion_tokens_from_options = None

            client = get_async_llm_client()
            try:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={
                        **self._chat_request_body(messages),
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    },
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise LLMProviderError(self._build_error_message(response))

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line == "data: [DONE]":
                            break
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                payload = json.loads(data_str)

                                # Extract stream usage if available
                                usage = payload.get("usage")
                                if isinstance(usage, dict):
                                    prompt_tokens_from_options = usage.get("prompt_tokens")
                                    completion_tokens_from_options = usage.get("completion_tokens")

                                choices = payload.get("choices")
                                if isinstance(choices, list) and choices:
                                    delta = choices[0].get("delta")
                                    if isinstance(delta, dict):
                                        content = delta.get("content")
                                        if content:
                                            accumulated_tokens_text.append(content)
                                            yield (STREAM_EVENT_TOKEN, content)
                            except json.JSONDecodeError:
                                continue
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"llm provider stream request failed: {exc}") from exc

            # Log tokens
            p_tokens = prompt_tokens_from_options
            c_tokens = completion_tokens_from_options

            if p_tokens is None or c_tokens is None:
                p_text = "".join(m.get("content", "") for m in messages)
                p_tokens = estimate_tokens(p_text)
                c_tokens = estimate_tokens("".join(accumulated_tokens_text))

            log_token_usage(
                model_name=self.config.model_name,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                operation_type=operation_type,
            )

        except (LLMProviderError, httpx.HTTPError) as exc:
            backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Stream chat")
            if backup_config is None:
                raise_provider_error(exc, "llm provider stream request failed")
            self.failover_triggered = failover_info
            yield (STREAM_EVENT_FAILOVER, failover_info)
            backup_provider = AsyncOpenAICompatibleProvider(backup_config)
            async for event in backup_provider.chat_stream(
                messages=messages,
                operation_type=operation_type,
                _retry_count=_retry_count + 1,
            ):
                yield event


def build_provider(config: LLMProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)


def build_async_provider(config: LLMProviderConfig) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(config)
