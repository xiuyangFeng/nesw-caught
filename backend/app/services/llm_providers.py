from __future__ import annotations

from collections.abc import AsyncGenerator
import json
import logging
from urllib.parse import urlparse

import httpx

from app.models.llm_provider_config import LLMProviderConfig
from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage

logger = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    pass


def find_backup_config(exclude_id: int) -> LLMProviderConfig | None:
    from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
    with SessionLocal() as session:
        return LLMProviderConfigRepository(session).get_backup(exclude_id)


def log_token_usage(model_name: str, prompt_tokens: int, completion_tokens: int, operation_type: str) -> None:
    try:
        with SessionLocal() as session:
            usage = LLMTokenUsage(
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                operation_type=operation_type,
            )
            session.add(usage)
            session.commit()
    except Exception as exc:
        logger.warning(f"Failed to log token usage to DB: {exc}")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Estimate roughly 1 token per 4 chars for English/Chinese blend
    return max(1, len(text) // 4)


class OpenAICompatibleProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def _validate_config(self) -> None:
        base_url = (self.config.base_url or "").strip()
        if not base_url:
            raise LLMProviderError("llm provider base url is not configured")

        hostname = (urlparse(base_url).hostname or "").lower()
        if hostname.endswith(".test") or hostname in {"example.com", "example.org", "example.net"}:
            raise LLMProviderError(f"llm provider uses placeholder base url: {base_url}")

        api_key = self.config.decrypted_api_key or ""
        if api_key.startswith("sk-test"):
            raise LLMProviderError("llm provider uses placeholder api key")

    def _request_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> str:
        try:
            self._validate_config()
            base_url = (self.config.base_url or "").rstrip("/")
            if not self.config.decrypted_api_key:
                raise LLMProviderError("llm provider api key is not configured")

            with httpx.Client(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.config.decrypted_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "news-caught/0.1",
                },
            ) as client:
                try:
                    response = client.post(
                        f"{base_url}/chat/completions",
                        json={
                            "model": self.config.model_name,
                            "messages": messages,
                            **({"response_format": response_format} if response_format else {}),
                        },
                    )
                except httpx.HTTPError as exc:
                    raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            if response.status_code >= 400:
                raise LLMProviderError(self._build_error_message(response))

            try:
                payload = response.json()
            except ValueError as exc:
                raise LLMProviderError("llm provider returned invalid json") from exc

            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not isinstance(choices, list) or not choices:
                raise LLMProviderError("llm provider returned no choices")

            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("llm provider returned empty content")

            # Extract usage
            usage = payload.get("usage") if isinstance(payload, dict) else None
            p_tokens = 0
            c_tokens = 0
            if isinstance(usage, dict):
                p_tokens = usage.get("prompt_tokens", 0)
                c_tokens = usage.get("completion_tokens", 0)
            else:
                p_text = "".join(m.get("content", "") for m in messages)
                p_tokens = estimate_tokens(p_text)
                c_tokens = estimate_tokens(content)

            log_token_usage(
                model_name=self.config.model_name,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                operation_type=operation_type,
            )

            return content

        except (LLMProviderError, httpx.HTTPError) as exc:
            if _retry_count < 1:
                backup_config = find_backup_config(getattr(self.config, "id", 0))
                if backup_config:
                    self.failover_triggered = {
                        "from_model": self.config.model_name,
                        "to_model": backup_config.model_name,
                        "reason": str(exc),
                    }
                    logger.warning(
                        f"Primary LLM provider {self.config.model_name} failed: {exc}. "
                        f"Retrying with backup provider: {backup_config.model_name}."
                    )
                    backup_provider = OpenAICompatibleProvider(backup_config)
                    return backup_provider._request_completion(
                        messages=messages,
                        response_format=response_format,
                        operation_type=operation_type,
                        _retry_count=_retry_count + 1,
                    )
            if isinstance(exc, LLMProviderError):
                raise exc
            raise LLMProviderError(f"llm provider request failed: {exc}") from exc

    def embed_text(self, text: str, _retry_count: int = 0) -> list[float]:
        try:
            self._validate_config()
            base_url = (self.config.base_url or "").rstrip("/")
            if not self.config.decrypted_api_key:
                raise LLMProviderError("llm provider api key is not configured")

            with httpx.Client(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.config.decrypted_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "news-caught/0.1",
                },
            ) as client:
                try:
                    response = client.post(
                        f"{base_url}/embeddings",
                        json={
                            "model": self.config.model_name,
                            "input": text,
                        },
                    )
                except httpx.HTTPError as exc:
                    raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            if response.status_code >= 400:
                raise LLMProviderError(self._build_error_message(response))

            try:
                payload = response.json()
            except ValueError as exc:
                raise LLMProviderError("llm provider returned invalid json") from exc

            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list) or not data:
                raise LLMProviderError("llm provider returned no embeddings")

            embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
            if not isinstance(embedding, list) or not embedding:
                raise LLMProviderError("llm provider returned empty embedding")

            # Log embedding token usage
            usage = payload.get("usage") if isinstance(payload, dict) else None
            p_tokens = 0
            if isinstance(usage, dict):
                p_tokens = usage.get("prompt_tokens", 0)
            else:
                p_tokens = estimate_tokens(text)

            log_token_usage(
                model_name=self.config.model_name,
                prompt_tokens=p_tokens,
                completion_tokens=0,
                operation_type="embedding",
            )

            return [float(value) for value in embedding]

        except (LLMProviderError, httpx.HTTPError) as exc:
            if _retry_count < 1:
                backup_config = find_backup_config(getattr(self.config, "id", 0))
                if backup_config:
                    logger.warning(
                        f"Embedding failed on primary provider {self.config.model_name}: {exc}. "
                        f"Retrying with backup provider: {backup_config.model_name}."
                    )
                    backup_provider = OpenAICompatibleProvider(backup_config)
                    return backup_provider.embed_text(text, _retry_count=_retry_count + 1)
            if isinstance(exc, LLMProviderError):
                raise exc
            raise LLMProviderError(f"llm provider request failed: {exc}") from exc

    def analyze_json(self, *, prompt: str) -> dict[str, object] | object:
        content = self._request_completion(
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
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("llm provider returned invalid analysis payload") from exc

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._request_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            operation_type="translate",
        )

    def test_connection(self) -> None:
        self.generate_text(
            system_prompt=(
                "This is a connection test. Reply with a very short plain text response. "
                "Do not use markdown, JSON, or extra explanation."
            ),
            user_prompt="ping",
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


class AsyncOpenAICompatibleProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def _validate_config(self) -> None:
        base_url = (self.config.base_url or "").strip()
        if not base_url:
            raise LLMProviderError("llm provider base url is not configured")

        hostname = (urlparse(base_url).hostname or "").lower()
        if hostname.endswith(".test") or hostname in {"example.com", "example.org", "example.net"}:
            raise LLMProviderError(f"llm provider uses placeholder base url: {base_url}")

        api_key = self.config.decrypted_api_key or ""
        if api_key.startswith("sk-test"):
            raise LLMProviderError("llm provider uses placeholder api key")

    async def _request_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> str:
        try:
            self._validate_config()
            base_url = (self.config.base_url or "").rstrip("/")
            if not self.config.decrypted_api_key:
                raise LLMProviderError("llm provider api key is not configured")

            async with httpx.AsyncClient(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.config.decrypted_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "news-caught/0.1",
                },
            ) as client:
                try:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        json={
                            "model": self.config.model_name,
                            "messages": messages,
                            **({"response_format": response_format} if response_format else {}),
                        },
                    )
                except httpx.HTTPError as exc:
                    raise LLMProviderError(f"llm provider request failed: {exc}") from exc

            if response.status_code >= 400:
                raise LLMProviderError(OpenAICompatibleProvider._build_error_message(response))

            try:
                payload = response.json()
            except ValueError as exc:
                raise LLMProviderError("llm provider returned invalid json") from exc

            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not isinstance(choices, list) or not choices:
                raise LLMProviderError("llm provider returned no choices")

            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("llm provider returned empty content")

            # Log token usage
            usage = payload.get("usage") if isinstance(payload, dict) else None
            p_tokens = 0
            c_tokens = 0
            if isinstance(usage, dict):
                p_tokens = usage.get("prompt_tokens", 0)
                c_tokens = usage.get("completion_tokens", 0)
            else:
                p_text = "".join(m.get("content", "") for m in messages)
                p_tokens = estimate_tokens(p_text)
                c_tokens = estimate_tokens(content)

            log_token_usage(
                model_name=self.config.model_name,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                operation_type=operation_type,
            )

            return content

        except (LLMProviderError, httpx.HTTPError) as exc:
            if _retry_count < 1:
                backup_config = find_backup_config(getattr(self.config, "id", 0))
                if backup_config:
                    self.failover_triggered = {
                        "from_model": self.config.model_name,
                        "to_model": backup_config.model_name,
                        "reason": str(exc),
                    }
                    logger.warning(
                        f"Async primary provider {self.config.model_name} failed: {exc}. "
                        f"Retrying with backup provider: {backup_config.model_name}."
                    )
                    backup_provider = AsyncOpenAICompatibleProvider(backup_config)
                    return await backup_provider._request_completion(
                        messages=messages,
                        response_format=response_format,
                        operation_type=operation_type,
                        _retry_count=_retry_count + 1,
                    )
            if isinstance(exc, LLMProviderError):
                raise exc
            raise LLMProviderError(f"llm provider request failed: {exc}") from exc

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return await self._request_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            operation_type="translate",
        )

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
    ) -> AsyncGenerator[str, None]:
        try:
            self._validate_config()
            base_url = (self.config.base_url or "").rstrip("/")
            if not self.config.decrypted_api_key:
                raise LLMProviderError("llm provider api key is not configured")

            accumulated_tokens_text = []
            prompt_tokens_from_options = None
            completion_tokens_from_options = None

            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.config.decrypted_api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "news-caught/0.1",
                        },
                        json={
                            "model": self.config.model_name,
                            "messages": messages,
                            "stream": True,
                            "stream_options": {"include_usage": True},
                        },
                    ) as response:
                        if response.status_code >= 400:
                            await response.read()
                            raise LLMProviderError(OpenAICompatibleProvider._build_error_message(response))

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
                                                yield content
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
            if _retry_count < 1:
                backup_config = find_backup_config(getattr(self.config, "id", 0))
                if backup_config:
                    logger.warning(
                        f"Stream chat failed on primary provider {self.config.model_name}: {exc}. "
                        f"Retrying with backup provider: {backup_config.model_name}."
                    )
                    yield f"[FAILOVER_SIGNAL]:{json.dumps({'from_model': self.config.model_name, 'to_model': backup_config.model_name, 'reason': str(exc)})}"
                    backup_provider = AsyncOpenAICompatibleProvider(backup_config)
                    async for token in backup_provider.chat_stream(
                        messages=messages,
                        operation_type=operation_type,
                        _retry_count=_retry_count + 1,
                    ):
                        yield token
                    return
            if isinstance(exc, LLMProviderError):
                raise exc
            raise LLMProviderError(f"llm provider stream request failed: {exc}") from exc


def build_provider(config: LLMProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)


def build_async_provider(config: LLMProviderConfig) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(config)
