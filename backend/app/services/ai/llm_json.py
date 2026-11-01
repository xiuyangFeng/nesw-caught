"""漏斗统一的 LLM 调用：只用"模型设置"里明确设为默认的模型，JSON 模式。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm_provider_config import LLMProviderConfig
from app.services.llm_providers import LLMProviderError, build_provider

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class JsonCompletionProvider(Protocol):
    def complete(self, *, messages: list[dict[str, str]], response_format: dict[str, str] | None = ...,
                 operation_type: str = ...) -> Any: ...


@dataclass
class FunnelModel:
    config_id: int
    model_name: str
    provider: JsonCompletionProvider


def get_explicit_default_config(session: Session) -> LLMProviderConfig | None:
    """明确设为默认且启用的模型配置。

    不沿用 ``get_default()`` 的"无默认则取最新启用"兜底：漏斗会持续花钱，
    必须由用户在模型设置里明确选定模型后才开始调用。
    """
    stmt = (
        select(LLMProviderConfig)
        .where(LLMProviderConfig.is_default.is_(True), LLMProviderConfig.is_active.is_(True))
        .order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id.desc())
    )
    return session.scalar(stmt)


def resolve_funnel_model(session: Session) -> FunnelModel | None:
    config = get_explicit_default_config(session)
    if config is None:
        return None
    return FunnelModel(config_id=config.id, model_name=config.model_name, provider=build_provider(config))


def complete_json(provider: JsonCompletionProvider, *, system: str, user: str, operation_type: str) -> Any:
    """调用一次并解析 JSON；返回内容不是合法 JSON 时抛 ``LLMProviderError``。"""
    result = provider.complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        operation_type=operation_type,
    )
    content = _FENCE_RE.sub("", (getattr(result, "content", "") or "").strip())
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(f"model returned invalid JSON: {content[:120]!r}") from exc
