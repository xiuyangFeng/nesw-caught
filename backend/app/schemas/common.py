from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def serialize_utc(value: datetime) -> str:
    """把 datetime 序列化成对外统一的 ISO-8601 Z 形式。

    公开导出：SSE 信封（app/api/routes/stream.py）也要用同一套 naive→UTC 规则，
    否则同一个 fetched_at 会在 REST 与 SSE 两条通道上给出不同的时间。
    """
    normalized = _normalize_utc(value)
    return normalized.isoformat().replace("+00:00", "Z")


# 历史私有别名：保留给既有 import 方，避免无谓的连锁改动。
_serialize_utc = serialize_utc


UTCDateTime = Annotated[
    datetime,
    AfterValidator(_normalize_utc),
    PlainSerializer(serialize_utc, return_type=str),
]

