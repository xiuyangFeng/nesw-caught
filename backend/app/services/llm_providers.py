from __future__ import annotations

import json

import httpx

from app.models.llm_provider_config import LLMProviderConfig


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def analyze_json(self, *, prompt: str) -> dict[str, object] | object:
        base_url = (self.config.base_url or "").rstrip("/")
        if not base_url:
            raise LLMProviderError("llm provider base url is not configured")
        if not self.config.api_key:
            raise LLMProviderError("llm provider api key is not configured")

        with httpx.Client(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "news-caught/0.1",
            },
        ) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": self.config.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You analyze a single news item for stock read-throughs. "
                                "Return JSON only with keys: top_pick, candidates, summary, risk_notes, sentiment, context_limitations."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )

        if response.status_code >= 400:
            raise LLMProviderError(f"llm provider request failed with status {response.status_code}")

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

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("llm provider returned invalid analysis payload") from exc


def build_provider(config: LLMProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)
