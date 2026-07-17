from __future__ import annotations

import base64
from datetime import UTC, datetime


def _normalize_cursor_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def encode_cursor(*, effective_at: datetime | None, item_id: int) -> str:
    normalized = _normalize_cursor_datetime(effective_at)
    timestamp = "" if normalized is None else normalized.isoformat()
    raw = f"{timestamp}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime | None, int]:
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(f"{cursor}{padding}").decode("utf-8")
    timestamp_text, item_id_text = raw.rsplit("|", 1)
    item_id = int(item_id_text)
    if not timestamp_text:
        return None, item_id
    effective_at = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    return _normalize_cursor_datetime(effective_at), item_id
