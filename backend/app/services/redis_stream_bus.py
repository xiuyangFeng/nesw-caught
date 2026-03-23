from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from redis import Redis


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


class RedisStreamPublisher:
    def __init__(
        self,
        *,
        redis_url: str,
        maxlen: int,
        timeout_seconds: float,
        client: Redis | None = None,
    ) -> None:
        self.client = client or Redis.from_url(redis_url, socket_timeout=timeout_seconds, decode_responses=True)
        self.maxlen = maxlen

    def publish(self, stream_name: str, payload: dict[str, object]) -> str:
        message = {
            "payload": json.dumps(payload, ensure_ascii=False, default=_json_default),
            "published_at": datetime.utcnow().isoformat() + "Z",
        }
        return str(self.client.xadd(stream_name, message, maxlen=self.maxlen, approximate=True))
