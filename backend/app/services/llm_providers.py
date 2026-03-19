from __future__ import annotations

import json

import httpx

from app.models.llm_provider_config import LLMProviderConfig


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def _request_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
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

        return content

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
            ]
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


def build_provider(config: LLMProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)
