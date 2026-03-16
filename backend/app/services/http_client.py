import httpx

from app.core.config import get_settings


class HttpClientFactory:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.settings.http_timeout_seconds,
            headers={"User-Agent": "news-caught/0.1"},
            follow_redirects=True,
        )
