from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.services.ingestion.types import LATENCY_EMA_ALPHA


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ema_latency(previous: float | None, latest: float) -> float:
    if previous is None:
        return latest
    return round(LATENCY_EMA_ALPHA * latest + (1 - LATENCY_EMA_ALPHA) * previous, 2)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_feed_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None

    try:
        return _normalize_datetime(parsedate_to_datetime(raw))
    except (TypeError, ValueError):
        pass

    normalized = raw.replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(normalized))
    except ValueError:
        return None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


def _canonicalize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, url.strip())
