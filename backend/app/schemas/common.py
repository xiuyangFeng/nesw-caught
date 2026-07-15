from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _serialize_utc(value: datetime) -> str:
    normalized = _normalize_utc(value)
    return normalized.isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[
    datetime,
    AfterValidator(_normalize_utc),
    PlainSerializer(_serialize_utc, return_type=str),
]

