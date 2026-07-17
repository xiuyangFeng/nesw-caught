from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from redis import Redis

logger = logging.getLogger(__name__)

InjectFn = Callable[[str, dict[str, Any]], None]


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def new_publisher_id() -> str:
    return uuid.uuid4().hex


class RedisStreamPublisher:
    def __init__(
        self,
        *,
        redis_url: str,
        maxlen: int,
        timeout_seconds: float,
        client: Redis | None = None,
        publisher_id: str | None = None,
    ) -> None:
        self.client = client or Redis.from_url(redis_url, socket_timeout=timeout_seconds, decode_responses=True)
        self.maxlen = maxlen
        self.publisher_id = publisher_id or new_publisher_id()

    def publish(self, stream_name: str, payload: dict[str, object], *, event_name: str | None = None) -> str:
        message = {
            "payload": json.dumps(payload, ensure_ascii=False, default=_json_default),
            "published_at": datetime.utcnow().isoformat() + "Z",
            "publisher_id": self.publisher_id,
        }
        if event_name:
            message["event_name"] = event_name
        return str(self.client.xadd(stream_name, message, maxlen=self.maxlen, approximate=True))


class RedisStreamConsumer:
    """Poll Redis streams and inject remote events into the local EventBus.

    Messages originating from this process (matching ``publisher_id``) are skipped
    to avoid echo when the same process also publishes to Redis.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        streams: Iterable[str],
        inject: InjectFn,
        timeout_seconds: float = 1.0,
        client: Redis | None = None,
        publisher_id: str | None = None,
        poll_interval_seconds: float = 0.5,
        block_ms: int = 500,
        initial_id: str = "$",
    ) -> None:
        self.client = client or Redis.from_url(redis_url, socket_timeout=timeout_seconds, decode_responses=True)
        self.streams = list(dict.fromkeys(streams))
        self.inject = inject
        self.publisher_id = publisher_id or new_publisher_id()
        self.poll_interval_seconds = max(poll_interval_seconds, 0.05)
        self.block_ms = max(int(block_ms), 1)
        self._initial_id = initial_id
        self._last_ids: dict[str, str] = {name: initial_id for name in self.streams}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def poll_once(self, *, count: int = 50) -> int:
        if not self.streams:
            return 0
        # First call with "$" only waits for new messages; subsequent reads use last ids.
        streams = dict(self._last_ids)
        try:
            # FakeRedis in tests ignores block; real redis uses short block.
            rows = self.client.xread(streams, count=count, block=self.block_ms)
        except TypeError:
            rows = self.client.xread(streams, count=count, block=0)
        except Exception:
            logger.exception("redis stream xread failed")
            return 0

        if not rows:
            # After the initial "$" subscription, switch to last seen ids so we
            # never replay the backlog on first connect; only live tail.
            for name in self.streams:
                if self._last_ids[name] == "$":
                    self._last_ids[name] = "$"
            return 0

        consumed = 0
        for stream_name, entries in rows:
            for entry_id, fields in entries:
                self._last_ids[str(stream_name)] = str(entry_id)
                if not self._handle_entry(dict(fields)):
                    continue
                consumed += 1
        return consumed

    def _handle_entry(self, fields: dict[str, str]) -> bool:
        remote_publisher = fields.get("publisher_id")
        if remote_publisher and remote_publisher == self.publisher_id:
            return False
        event_name = fields.get("event_name")
        if not event_name:
            return False
        raw_payload = fields.get("payload") or "{}"
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("invalid redis stream payload for event %s", event_name)
            return False
        if not isinstance(payload, dict):
            logger.warning("redis stream payload for %s is not an object", event_name)
            return False
        self.inject(event_name, payload)
        return True

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="redis-stream-consumer", daemon=True)
        self._thread.start()

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=join_timeout)
        self._thread = None

    def _run(self) -> None:
        self._last_ids = {name: self._initial_id for name in self.streams}
        while not self._stop.is_set():
            try:
                consumed = self.poll_once()
                if consumed == 0:
                    time.sleep(self.poll_interval_seconds)
            except Exception:
                logger.exception("redis stream consumer loop failed")
                time.sleep(self.poll_interval_seconds)
