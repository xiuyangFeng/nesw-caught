from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlparse

import anyio
import httpx

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.llm_provider_config import LLMProviderConfig
from app.services.http_pool import get_async_llm_client, get_llm_client
from app.services.token_usage_buffer import token_usage_buffer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Stream event types yielded by AsyncOpenAICompatibleProvider.chat_stream.
STREAM_EVENT_TOKEN = "token"
STREAM_EVENT_FAILOVER = "failover"

# ("token", str) | ("failover", dict[str, str])
StreamEvent = tuple[str, "str | dict[str, str]"]


class LLMProviderError(RuntimeError):
    """LLM provider 调用失败。

    携带 ``status_code``（HTTP 响应状态码，非 HTTP 层错误时为 None）与
    ``retryable``（是否允许对同一 provider 做有限次重试），供 `is_retryable_error`
    判定重试策略：httpx 超时/网络错误、429、5xx 视为瞬态错误可重试；其余 4xx
    （如 400/401/404）判定为不可重试，直接进入既有的单次 failover 判定。
    """

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


# —— 可观测性:计量/缓存这类"旁路"写入失败时历来只 log warning 就吞掉,不影响主
# 分类流程(保持这个"最佳努力"语义),但此前完全不可观测。这里只加进程内计数,
# 由 `BackgroundQueueWorker` 周期性读取并把增量回写到既有 `worker_runtime_status` 表。
_llm_metrics_lock = threading.Lock()
_llm_error_counts: dict[str, int] = {
    "token_usage_log_failed": 0,
    "classification_cache_read_failed": 0,
    "classification_cache_write_failed": 0,
}


def get_llm_provider_error_counts() -> dict[str, int]:
    """返回本模块内累计的(被吞掉的)异常计数快照,供上层 worker 周期性上报。"""
    with _llm_metrics_lock:
        return dict(_llm_error_counts)


def _incr_llm_error(key: str) -> None:
    with _llm_metrics_lock:
        _llm_error_counts[key] = _llm_error_counts.get(key, 0) + 1


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
        # 可恢复:计量丢失不影响本次 LLM 调用结果,继续走既有"最佳努力"语义。
        logger.warning(f"Failed to log token usage to DB: {exc}")
        _incr_llm_error("token_usage_log_failed")


def normalize_classification_content(content: str) -> str:
    """归一化分类内容：去除首尾空白并折叠内部连续空白，保证等价内容命中同一缓存。"""
    return " ".join((content or "").split())


def compute_classification_hash(content: str) -> str:
    """返回归一化内容的 sha256 十六进制摘要，作为分类缓存键。"""
    normalized = normalize_classification_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_classification_fields_hash(title: str, summary: str | None, market: str | None) -> str:
    """按 (title, summary, market) 计算分类缓存键。

    正文唯一导致以整篇 prompt 为键时命中率≈0;改为结构化字段键后,
    相同标题+摘要+市场的新闻(如同题转载)直接命中缓存。
    """
    normalized = "\x1f".join(normalize_classification_content(part or "") for part in (title, summary, market))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_classification(content_hash: str, session: Session | None = None) -> str | None:
    """按内容 hash 读取缓存的分类结果 JSON；读取失败静默降级为未命中。

    调用方已有 session 时可传入复用,否则自开一个 SessionLocal。
    """
    from app.repositories.llm_classification_cache_repository import (
        LLMClassificationCacheRepository,
    )

    try:
        if session is not None:
            entry = LLMClassificationCacheRepository(session).get_by_hash(content_hash)
            return entry.result_json if entry is not None else None
        with SessionLocal() as owned_session:
            entry = LLMClassificationCacheRepository(owned_session).get_by_hash(content_hash)
            return entry.result_json if entry is not None else None
    except Exception as exc:
        # 可恢复:读缓存失败按未命中处理,回退到正常 LLM 调用,不影响正确性。
        logger.warning(f"Failed to read classification cache: {exc}")
        _incr_llm_error("classification_cache_read_failed")
        return None


def store_classification(content_hash: str, result_json: str, model_name: str | None, session: Session | None = None) -> None:
    """写入分类结果缓存；写入失败仅告警，绝不影响主分类流程。

    调用方已有 session 时可传入复用(提交边界归调用方),否则自开 SessionLocal 并提交。
    """
    from app.repositories.llm_classification_cache_repository import (
        LLMClassificationCacheRepository,
    )

    try:
        if session is not None:
            LLMClassificationCacheRepository(session).upsert(
                content_hash=content_hash,
                result_json=result_json,
                model_name=model_name,
            )
            return
        with SessionLocal() as owned_session:
            LLMClassificationCacheRepository(owned_session).upsert(
                content_hash=content_hash,
                result_json=result_json,
                model_name=model_name,
            )
            owned_session.commit()
    except Exception as exc:
        # 可恢复:写缓存失败只是丢失这次缓存收益,不影响本次分类结果的正确性。
        logger.warning(f"Failed to write classification cache: {exc}")
        _incr_llm_error("classification_cache_write_failed")


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


def parse_embeddings_response(
    payload: object, expected_count: int
) -> tuple[list[list[float]], dict[str, object] | None]:
    """Parse a batch OpenAI-compatible embeddings payload into (vectors, usage).

    ``data`` items are not guaranteed to come back in request order, so each
    vector is placed at its reported ``index`` (falling back to array position
    when a provider omits it) before being returned in ``0..expected_count-1``
    order.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise LLMProviderError("llm provider returned no embeddings")

    indexed: list[tuple[int, list[float]]] = []
    for position, item in enumerate(data):
        embedding = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(embedding, list) or not embedding:
            raise LLMProviderError("llm provider returned empty embedding")
        raw_index = item.get("index") if isinstance(item, dict) else None
        index = raw_index if isinstance(raw_index, int) else position
        indexed.append((index, [float(value) for value in embedding]))

    indexed.sort(key=lambda pair: pair[0])
    vectors = [vector for _, vector in indexed]
    if len(vectors) != expected_count:
        raise LLMProviderError(
            f"llm provider returned {len(vectors)} embeddings, expected {expected_count}"
        )

    usage = payload.get("usage") if isinstance(payload, dict) else None
    return vectors, usage if isinstance(usage, dict) else None


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


def is_retryable_error(exc: Exception) -> bool:
    """判断是否允许对同一 provider 做有限次重试（failover 之前）。

    可重试：httpx 传输层错误（超时/连接失败等，此处捕获到的均未经过
    ``raise_for_status``，因此只会是网络/超时类错误）、HTTP 429、HTTP 5xx。
    不可重试：除 429 外的其余 4xx（如 400/401/404），以及非 HTTP 的解析/校验错误。
    """
    if isinstance(exc, LLMProviderError):
        return exc.retryable
    return isinstance(exc, httpx.HTTPError)


def compute_backoff_delay(base_seconds: float, attempt: int) -> float:
    """第 ``attempt``（从 0 开始）次重试前的退避时长：指数退避 + 抖动。

    默认 base=0.5s 时对应 0.5s / 1s / 2s ... 的基础退避序列，另外叠加最多
    25% 基础延迟的随机抖动，避免瞬态错误恢复瞬间多个请求同时重试造成的惊群。
    """
    base_seconds = max(0.0, base_seconds)
    delay = base_seconds * (2**attempt)
    jitter = random.uniform(0, delay * 0.25) if delay > 0 else 0.0
    return delay + jitter


def _retry_sleep(seconds: float) -> None:
    """同 provider 重试前的同步退避 sleep；测试可 monkeypatch 此函数来加速/断言退避调用。"""
    time.sleep(seconds)


async def _retry_sleep_async(seconds: float) -> None:
    """同 provider 重试前的异步退避 sleep；测试可 monkeypatch 此函数来加速/断言退避调用。"""
    await anyio.sleep(seconds)


def _is_retryable_status(status_code: int) -> bool:
    """HTTP 状态码是否属于可重试的瞬态错误：429 或 5xx。"""
    return status_code == 429 or status_code >= 500


class _BaseOpenAICompatibleProvider:
    """Shared config validation, request preparation and response handling.

    Subclasses only implement the transport layer (sync vs async httpx).
    """

    def __init__(self, config: LLMProviderConfig, *, max_attempts: int | None = None) -> None:
        self.config = config
        self.failover_triggered: dict[str, str] | None = None
        # None（默认，主 provider 走这条路）= 使用 settings 里配置的
        # llm_retry_max_attempts；显式传入非 None 值（failover 构造 backup provider
        # 时用）会覆盖 settings，用于收紧/放宽这一个 provider 实例的同 provider 重试预算。
        # 具体见 `_resolve_max_attempts`。
        self._max_attempts_override = max_attempts

    def _resolve_max_attempts(self) -> int:
        """本 provider 实例允许的"同 provider 重试"次数上限（不含首次尝试）。

        failover 之后接手的 backup provider 会以 ``max_attempts=0`` 构造：backup
        只做单次尝试、不再重复走一整套重试预算，避免 primary 重试耗尽 + backup 又
        整套重试导致的双倍等待（最坏情况下退避总时长翻倍甚至更多）。
        """
        if self._max_attempts_override is not None:
            return self._max_attempts_override
        return get_settings().llm_retry_max_attempts

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
    ) -> CompletionResult:
        """解析响应为 CompletionResult；不做 token 计量写入(由调用方在成功后处理，
        sync/async 两种 provider 的落库路径不同，见各自 complete())。"""
        if response.status_code >= 400:
            raise LLMProviderError(
                self._build_error_message(response),
                status_code=response.status_code,
                retryable=_is_retryable_status(response.status_code),
            )

        payload = decode_json_response(response)
        content, usage = parse_chat_completion(payload)
        prompt_tokens, completion_tokens = resolve_completion_usage(usage, messages, content)

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
    def _next_retry_delay(self, attempt: int) -> float:
        return compute_backoff_delay(get_settings().llm_retry_backoff_seconds, attempt)

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        operation_type: str = "chat",
        _retry_count: int = 0,
    ) -> CompletionResult:
        max_attempts = self._resolve_max_attempts()
        attempt = 0
        while True:
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
                    raise LLMProviderError(f"llm provider request failed: {exc}", retryable=True) from exc

                result = self._handle_completion_response(response, messages)
                log_token_usage(
                    model_name=self.config.model_name,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    operation_type=operation_type,
                )
                return result

            except (LLMProviderError, httpx.HTTPError) as exc:
                if attempt < max_attempts and is_retryable_error(exc):
                    _retry_sleep(self._next_retry_delay(attempt))
                    attempt += 1
                    continue

                backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Chat completion")
                if backup_config is None:
                    raise_provider_error(exc, "llm provider request failed")
                self.failover_triggered = failover_info
                result = OpenAICompatibleProvider(backup_config, max_attempts=0).complete(
                    messages=messages,
                    response_format=response_format,
                    operation_type=operation_type,
                    _retry_count=_retry_count + 1,
                )
                result.failover = failover_info
                return result

    def embed_text(self, text: str, _retry_count: int = 0) -> list[float]:
        max_attempts = self._resolve_max_attempts()
        attempt = 0
        while True:
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
                    raise LLMProviderError(f"llm provider request failed: {exc}", retryable=True) from exc

                if response.status_code >= 400:
                    raise LLMProviderError(
                        self._build_error_message(response),
                        status_code=response.status_code,
                        retryable=_is_retryable_status(response.status_code),
                    )

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
                if attempt < max_attempts and is_retryable_error(exc):
                    _retry_sleep(self._next_retry_delay(attempt))
                    attempt += 1
                    continue

                backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Embedding")
                if backup_config is None:
                    raise_provider_error(exc, "llm provider request failed")
                self.failover_triggered = failover_info
                return OpenAICompatibleProvider(backup_config, max_attempts=0).embed_text(
                    text, _retry_count=_retry_count + 1
                )

    def embed_texts(self, texts: list[str], _retry_count: int = 0) -> list[list[float]]:
        """批量 embedding：一次 `/embeddings` 请求传入整批文本，按响应 index 对齐返回。

        调用方（如 stock_research_synthesis._rank_news）借此把逐条串行 embedding
        调用合并为单次批量请求，避免 N 次串行外部 IO。空列表直接返回空列表，不发请求。
        """
        if not texts:
            return []

        max_attempts = self._resolve_max_attempts()
        attempt = 0
        while True:
            try:
                base_url, headers = self._prepare_request()
                client = get_llm_client()
                try:
                    response = client.post(
                        f"{base_url}/embeddings",
                        headers=headers,
                        json={"model": self.config.model_name, "input": texts},
                    )
                except httpx.HTTPError as exc:
                    raise LLMProviderError(f"llm provider request failed: {exc}", retryable=True) from exc

                if response.status_code >= 400:
                    raise LLMProviderError(
                        self._build_error_message(response),
                        status_code=response.status_code,
                        retryable=_is_retryable_status(response.status_code),
                    )

                payload = decode_json_response(response)
                embeddings, usage = parse_embeddings_response(payload, expected_count=len(texts))

                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens", 0)
                else:
                    prompt_tokens = sum(estimate_tokens(text) for text in texts)

                log_token_usage(
                    model_name=self.config.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    operation_type="embedding",
                )
                return embeddings

            except (LLMProviderError, httpx.HTTPError) as exc:
                if attempt < max_attempts and is_retryable_error(exc):
                    _retry_sleep(self._next_retry_delay(attempt))
                    attempt += 1
                    continue

                backup_config, failover_info = plan_failover(self.config, exc, _retry_count, "Batch embedding")
                if backup_config is None:
                    raise_provider_error(exc, "llm provider request failed")
                self.failover_triggered = failover_info
                return OpenAICompatibleProvider(backup_config, max_attempts=0).embed_texts(
                    texts, _retry_count=_retry_count + 1
                )

    def analyze_json(
        self,
        *,
        prompt: str,
        title: str | None = None,
        summary: str | None = None,
        market: str | None = None,
    ) -> dict[str, object] | object:
        # 分类缓存：相同内容命中缓存则直接返回，跳过 LLM 调用与 token 计量。
        # 提供 title 时按 (title+summary+market) 建键(相同标题新闻命中);
        # 否则回退到整篇 prompt 建键(保持旧调用方行为)。
        cache_enabled = get_settings().llm_classification_cache_enabled
        content_hash: str | None = None
        if cache_enabled:
            content_hash = (
                compute_classification_fields_hash(title, summary, market)
                if title is not None
                else compute_classification_hash(prompt)
            )
            cached_json = get_cached_classification(content_hash)
            if cached_json is not None:
                try:
                    return json.loads(cached_json)
                except json.JSONDecodeError:
                    # 缓存内容损坏则忽略缓存，回退到正常 LLM 调用。
                    logger.warning("Discarding corrupted classification cache entry")

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
            parsed = json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("llm provider returned invalid analysis payload") from exc

        if cache_enabled and content_hash is not None:
            store_classification(content_hash, result.content, self.config.model_name)
        return parsed

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
        settings = get_settings()
        max_attempts = self._resolve_max_attempts()
        backoff_base = settings.llm_retry_backoff_seconds
        attempt = 0
        while True:
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
                    raise LLMProviderError(f"llm provider request failed: {exc}", retryable=True) from exc

                result = self._handle_completion_response(response, messages)
                # token 计量落库是同步 DB 写(TokenUsageBuffer 攒批触发 flush 时会开
                # SessionLocal 提交)，丢到独立线程执行，避免占用事件循环线程。
                await anyio.to_thread.run_sync(
                    log_token_usage,
                    self.config.model_name,
                    result.prompt_tokens,
                    result.completion_tokens,
                    operation_type,
                )
                return result

            except (LLMProviderError, httpx.HTTPError) as exc:
                if attempt < max_attempts and is_retryable_error(exc):
                    await _retry_sleep_async(compute_backoff_delay(backoff_base, attempt))
                    attempt += 1
                    continue

                # plan_failover 内部同步读 DB(find_backup_config open 一个
                # SessionLocal)，同样丢到独立线程执行，避免占用事件循环线程。
                backup_config, failover_info = await anyio.to_thread.run_sync(
                    plan_failover, self.config, exc, _retry_count, "Async chat completion"
                )
                if backup_config is None:
                    raise_provider_error(exc, "llm provider request failed")
                self.failover_triggered = failover_info
                result = await AsyncOpenAICompatibleProvider(backup_config, max_attempts=0).complete(
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

        同 provider 重试仅允许发生在"首字节前"：一旦已经向调用方 yield 过至少一个
        token（``first_byte_sent``），流中断就不再重试同一 provider（重新发起会
        产生重复/错乱的内容），而是直接按既有语义判定是否 failover。
        """
        settings = get_settings()
        max_attempts = self._resolve_max_attempts()
        backoff_base = settings.llm_retry_backoff_seconds
        attempt = 0
        first_byte_sent = False
        while True:
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
                            raise LLMProviderError(
                                self._build_error_message(response),
                                status_code=response.status_code,
                                retryable=_is_retryable_status(response.status_code),
                            )

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
                                                first_byte_sent = True
                                                yield (STREAM_EVENT_TOKEN, content)
                                except json.JSONDecodeError:
                                    continue
                except httpx.HTTPError as exc:
                    raise LLMProviderError(f"llm provider stream request failed: {exc}", retryable=True) from exc

                # Log tokens
                p_tokens = prompt_tokens_from_options
                c_tokens = completion_tokens_from_options

                if p_tokens is None or c_tokens is None:
                    p_text = "".join(m.get("content", "") for m in messages)
                    p_tokens = estimate_tokens(p_text)
                    c_tokens = estimate_tokens("".join(accumulated_tokens_text))

                await anyio.to_thread.run_sync(
                    log_token_usage,
                    self.config.model_name,
                    p_tokens,
                    c_tokens,
                    operation_type,
                )
                return

            except (LLMProviderError, httpx.HTTPError) as exc:
                if not first_byte_sent and attempt < max_attempts and is_retryable_error(exc):
                    await _retry_sleep_async(compute_backoff_delay(backoff_base, attempt))
                    attempt += 1
                    continue

                backup_config, failover_info = await anyio.to_thread.run_sync(
                    plan_failover, self.config, exc, _retry_count, "Stream chat"
                )
                if backup_config is None:
                    raise_provider_error(exc, "llm provider stream request failed")
                self.failover_triggered = failover_info
                yield (STREAM_EVENT_FAILOVER, failover_info)
                backup_provider = AsyncOpenAICompatibleProvider(backup_config, max_attempts=0)
                async for event in backup_provider.chat_stream(
                    messages=messages,
                    operation_type=operation_type,
                    _retry_count=_retry_count + 1,
                ):
                    yield event
                return


def build_provider(config: LLMProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)


def build_async_provider(config: LLMProviderConfig) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(config)
