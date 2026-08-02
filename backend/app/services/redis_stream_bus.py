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
        # socket_connect_timeout 必须显式给：只设 socket_timeout 时，redis-py 的建连
        # 阶段（DNS + TCP handshake）不受它约束，Redis 主机不可达时 publish 可能远超
        # 预期的 timeout_seconds 预算 —— 而 publish 是在 ingestion 串行落库线程里
        # 同步调用的，超时预算失效会直接把落库线程拖住。
        self.client = client or Redis.from_url(
            redis_url,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
            decode_responses=True,
        )
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
        error_log_interval_seconds: float = 60.0,
    ) -> None:
        # socket_connect_timeout 必须显式给：只设 socket_timeout 时，redis-py 的建连
        # 阶段（DNS + TCP handshake）不受它约束，Redis 主机不可达时 publish 可能远超
        # 预期的 timeout_seconds 预算 —— 而 publish 是在 ingestion 串行落库线程里
        # 同步调用的，超时预算失效会直接把落库线程拖住。
        self.client = client or Redis.from_url(
            redis_url,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
            decode_responses=True,
        )
        self.streams = list(dict.fromkeys(streams))
        self.inject = inject
        self.publisher_id = publisher_id or new_publisher_id()
        self.poll_interval_seconds = max(poll_interval_seconds, 0.05)
        self.block_ms = max(int(block_ms), 1)
        self._initial_id = initial_id
        self._last_ids: dict[str, str] = {name: initial_id for name in self.streams}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # 异常日志降频:redis 持续故障时每 interval 最多一条,避免刷屏。
        self.error_log_interval_seconds = max(error_log_interval_seconds, 0.0)
        self._last_error_log_at = float("-inf")

    def _log_error_throttled(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log_at >= self.error_log_interval_seconds:
            self._last_error_log_at = now
            logger.exception(message)

    def resolve_initial_ids(self) -> None:
        """把初始的 "$" 解析成各 stream 当前的真实 last-id。

        必须这么做的原因（多进程模式下这是主事件通路，丢消息不可接受）：
        "$" 的语义是"只要本次 XREAD 调用之后新产生的消息"。而消费循环是
        `xread(block=500ms)` + 无消息时 `sleep(500ms)`，只要一直没收到消息，
        `_last_ids` 就一直停在 "$" —— 于是**落在 sleep 空窗里的消息永久丢失**
        （"$" 不会推进，下一次 XREAD 只看它自己之后的新消息）。实测单发一条
        news.created_batch 约 50% 概率丢。

        解析成显式 id 之后，每轮都从"上次读到的位置"续读，空窗期间产生的消息
        会在下一轮被补上，不再依赖 30s 的 DB 兜底扫描来兜底。
        解析时取的是"当前最后一条"，因此仍然不会重放历史积压（保持只跟新的语义）。
        """
        for name in self.streams:
            if self._last_ids.get(name) != "$":
                continue
            last_id = "0-0"
            try:
                info = self.client.xinfo_stream(name)
                candidate = info.get("last-generated-id") if isinstance(info, dict) else None
                if candidate:
                    last_id = str(candidate)
            except Exception:
                # stream 尚不存在（还没有人 XADD 过）→ 从 0 开始读；该 stream 本来
                # 也没有历史消息，不存在重放风险。客户端不支持 xinfo_stream（测试
                # 里的 FakeRedis）→ 同样退回 "0-0"，行为退化为"从头读"，测试语义
                # 不受影响（FakeRedis 里没有历史积压）。
                last_id = "0-0"
            self._last_ids[name] = last_id

    def poll_once(self, *, count: int = 50) -> int:
        if not self.streams:
            return 0
        self.resolve_initial_ids()
        streams = dict(self._last_ids)
        try:
            # FakeRedis in tests ignores block; real redis uses short block.
            rows = self.client.xread(streams, count=count, block=self.block_ms)
        except TypeError:
            rows = self.client.xread(streams, count=count, block=0)
        except Exception:
            self._log_error_throttled(f"redis stream xread failed: streams={self.streams}")
            return 0

        if not rows:
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
                self._log_error_throttled(f"redis stream consumer loop failed: streams={self.streams}")
                time.sleep(self.poll_interval_seconds)
