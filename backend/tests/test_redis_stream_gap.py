"""消费者不得因为「轮询空窗」丢消息。

多进程模式（PIPELINE_WORKERS_ENABLED=false + 独立 pipeline worker 进程）下，
Redis stream 是 news.created_batch 从抓取侧送到 pipeline 侧的**主通路**，丢消息
就意味着新闻只能靠 30s 的 DB 兜底扫描被捡起来，时效性直接退化。

修复前：`_last_ids` 初值是 "$"（语义为「只要本次 XREAD 之后新产生的消息」），而
消费循环是 `xread(block=500ms)` + 无消息时 `sleep(500ms)`。只要一直没收到消息，
`_last_ids` 就一直停在 "$"，**落在 sleep 空窗里产生的消息永久丢失**。
对真实 Redis 实测：连发 10 条丢 1 条；单发一条丢失概率约 50%。

修复：开跑前把 "$" 解析成各 stream 当前真实的 last-id，之后始终按显式 id 续读。
"""

from __future__ import annotations

from app.services.redis_stream_bus import RedisStreamConsumer


class GapFakeRedis:
    """按 Redis 的真实语义实现 "$"：只返回本次调用之后新产生的消息。

    这是复现该 bug 的关键——仓库里既有的 FakeRedis 对 "$" 直接 `continue`
    （永远不返回任何东西），反而掩盖了「空窗丢消息」这个具体形态。
    """

    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, str]]] = []
        self._seq = 0

    def xadd(self, stream_name: str, message: dict[str, str], **kwargs) -> str:
        del stream_name, kwargs
        self._seq += 1
        entry_id = f"{self._seq}-0"
        self.entries.append((entry_id, dict(message)))
        return entry_id

    def xinfo_stream(self, name: str) -> dict[str, str]:
        del name
        if not self.entries:
            raise RuntimeError("no such key")
        return {"last-generated-id": self.entries[-1][0]}

    def xread(self, streams: dict[str, str], count: int = 50, block: int = 0):
        del block
        result = []
        for stream_name, last_id in streams.items():
            batch = []
            for entry_id, fields in self.entries:
                # "$" = 只要「本次调用之后」的消息 → 本次调用一律返回空。
                if last_id == "$":
                    continue
                if _greater(entry_id, last_id):
                    batch.append((entry_id, fields))
                    if len(batch) >= count:
                        break
            if batch:
                result.append((stream_name, batch))
        return result


def _parse_id(entry_id: str) -> tuple[int, int]:
    ms, _, seq = entry_id.partition("-")
    return int(ms), int(seq or 0)


def _greater(left: str, right: str) -> bool:
    """按 Redis 语义**数值**比较 entry id。

    注意不能用字符串比较：`"10-0" > "9-0"` 在字符串序下是 False，会让第 10 条
    之后的消息被静默跳过——这是写这个 fake 时踩到的坑，跟被测代码无关。
    """
    if right in {"0", "0-0", "-"}:
        return True
    return _parse_id(left) > _parse_id(right)


def _message(index: int) -> dict[str, str]:
    return {
        "payload": f'{{"n": {index}}}',
        "published_at": "2026-07-26T00:00:00Z",
        "publisher_id": "producer-process",
        "event_name": "news.created_batch",
    }


def _build_consumer(client: GapFakeRedis, received: list[str]) -> RedisStreamConsumer:
    def inject(event_name: str, payload: dict, occurred_at=None, **kwargs) -> bool:
        del event_name, occurred_at, kwargs
        received.append(str(payload))
        return True

    return RedisStreamConsumer(
        redis_url="redis://unused",
        streams=["stream:news:ingested"],
        inject=inject,
        client=client,
        publisher_id="consumer-process",
    )


def test_message_published_in_poll_gap_is_not_lost() -> None:
    """消息在两次 poll 之间产生（模拟 sleep 空窗），必须仍被收到。"""
    client = GapFakeRedis()
    received: list[str] = []
    consumer = _build_consumer(client, received)

    # 第一次轮询：此刻 stream 还是空的，且 _last_ids 尚未解析。
    consumer.poll_once()
    assert received == []

    # 空窗期：生产者 XADD 一条。
    client.xadd("stream:news:ingested", _message(1))

    # 下一轮必须补上这条。修复前 _last_ids 仍是 "$"，这里会永远收不到。
    consumer.poll_once()
    assert len(received) == 1, "落在轮询空窗里的消息被丢失了"


def test_multiple_gap_messages_all_delivered() -> None:
    client = GapFakeRedis()
    received: list[str] = []
    consumer = _build_consumer(client, received)

    consumer.poll_once()
    for i in range(10):
        client.xadd("stream:news:ingested", _message(i))
        consumer.poll_once()

    assert len(received) == 10


def test_existing_backlog_is_not_replayed() -> None:
    """解析成显式 id 不能带来副作用：连接前的历史积压仍然不重放。"""
    client = GapFakeRedis()
    for i in range(5):
        client.xadd("stream:news:ingested", _message(i))

    received: list[str] = []
    consumer = _build_consumer(client, received)
    consumer.poll_once()

    assert received == [], "不应重放连接前的历史消息"

    client.xadd("stream:news:ingested", _message(99))
    consumer.poll_once()
    assert len(received) == 1


def test_resolve_is_idempotent_and_does_not_rewind() -> None:
    """重复调用 resolve 不能把已经推进的位点回退。"""
    client = GapFakeRedis()
    received: list[str] = []
    consumer = _build_consumer(client, received)

    client.xadd("stream:news:ingested", _message(1))
    consumer.poll_once()
    consumer.poll_once()
    advanced = dict(consumer._last_ids)

    consumer.resolve_initial_ids()
    assert consumer._last_ids == advanced


def test_missing_stream_starts_from_beginning() -> None:
    """stream 尚不存在时退回 0-0，之后产生的消息照常收到。"""
    client = GapFakeRedis()
    received: list[str] = []
    consumer = _build_consumer(client, received)

    consumer.resolve_initial_ids()
    assert consumer._last_ids["stream:news:ingested"] == "0-0"

    client.xadd("stream:news:ingested", _message(1))
    consumer.poll_once()
    assert len(received) == 1
