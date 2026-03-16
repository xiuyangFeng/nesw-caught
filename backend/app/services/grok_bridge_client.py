from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class GrokBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class GrokBridgeHealth:
    status: str
    url: str | None
    on_grok: bool
    version: str | None


class GrokBridgeClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.x_monitor_enabled

    @property
    def configured(self) -> bool:
        return bool(self.settings.grok_bridge_base_url)

    def _client(self, timeout_seconds: float | None = None) -> httpx.Client:
        if not self.configured:
            raise GrokBridgeError("grok bridge base url is not configured")

        return httpx.Client(
            base_url=self.settings.grok_bridge_base_url,
            timeout=timeout_seconds or self.settings.grok_bridge_timeout_seconds,
            headers={"User-Agent": "news-caught/0.1"},
        )

    def health(self) -> GrokBridgeHealth:
        try:
            with self._client() as client:
                response = client.get("/health")
        except httpx.TimeoutException as exc:
            raise GrokBridgeError("grok bridge health request timed out") from exc
        except httpx.HTTPError as exc:
            raise GrokBridgeError(f"grok bridge health request failed: {exc}") from exc

        if response.status_code != 200:
            raise GrokBridgeError(f"grok bridge health request failed with status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise GrokBridgeError("grok bridge health returned invalid json") from exc

        return GrokBridgeHealth(
            status=str(payload.get("status") or "unknown"),
            url=str(payload.get("url")) if payload.get("url") else None,
            on_grok=bool(payload.get("on_grok")),
            version=str(payload.get("version")) if payload.get("version") else None,
        )

    def chat(self, prompt: str, timeout_seconds: float | None = None) -> str:
        if not prompt.strip():
            raise GrokBridgeError("prompt is empty")

        timeout = timeout_seconds or self.settings.grok_bridge_timeout_seconds
        try:
            with self._client(timeout_seconds=timeout + 5) as client:
                response = client.post("/chat", json={"prompt": prompt, "timeout": timeout})
        except httpx.TimeoutException as exc:
            raise GrokBridgeError("grok bridge chat request timed out") from exc
        except httpx.HTTPError as exc:
            raise GrokBridgeError(f"grok bridge chat request failed: {exc}") from exc

        if response.status_code != 200:
            raise GrokBridgeError(f"grok bridge chat request failed with status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise GrokBridgeError("grok bridge chat returned invalid json") from exc

        response_status = str(payload.get("status") or "error")
        response_text = payload.get("response")
        if response_status not in {"ok", "timeout"}:
            error = payload.get("error") or "unknown grok bridge error"
            raise GrokBridgeError(str(error))
        if not isinstance(response_text, str) or not response_text.strip():
            raise GrokBridgeError("grok bridge returned empty response")
        return response_text
