"""WS-1 读路径并发与连接池回归测试。

覆盖 2026-07-25 读路径重构的四个改动面：
1. SimpleTTLCache：TTL 过期 / LRU 容量淘汰 / 多线程并发安全 / clear；
2. db.session.engine：显式 QueuePool 配置生效、内存库仍走 StaticPool 语义；
3. SSE：跨线程 publish 能被收到、循环不再走 anyio 线程池、有界队列不阻塞发布方；
4. SSE handler 生命周期：连接结束后订阅数归位；响应体从未被迭代时不残留 handler。
"""

import asyncio
import inspect
import threading
import time
from pathlib import Path

import anyio
import pytest
from sqlalchemy.pool import QueuePool, StaticPool

from app.api.routes import stream as stream_route
from app.core.config import get_settings
from app.core.simple_cache import SimpleTTLCache
from app.db import session as db_session
from app.services.event_bus import InMemoryEventBus

# ---------------------------------------------------------------------------
# 1. SimpleTTLCache
# ---------------------------------------------------------------------------


def test_cache_entry_expires_after_ttl(monkeypatch) -> None:
    cache = SimpleTTLCache(ttl=5.0, enabled=True)
    now = time.time()
    monkeypatch.setattr("app.core.simple_cache.time.time", lambda: now)
    cache.set("k", "v")
    assert cache.get("k") == "v"

    monkeypatch.setattr("app.core.simple_cache.time.time", lambda: now + 5.1)
    assert cache.get("k") is None
    # 过期条目必须被就地清掉，而不是继续占着内存
    assert "k" not in cache._cache


def test_cache_evicts_least_recently_used_when_over_capacity() -> None:
    cache = SimpleTTLCache(ttl=60.0, enabled=True, max_entries=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    # 读一下 "a"，让它变成最近使用；此时最久未使用的是 "b"
    assert cache.get("a") == 1

    cache.set("d", 4)

    assert len(cache._cache) == 3
    assert cache.get("b") is None, "LRU 应淘汰最久未使用的 b"
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("d") == 4


def test_cache_never_exceeds_max_entries_under_key_flood() -> None:
    """feed-layout 的 key 由查询参数拼成，任意 URL 都能造新 key —— 必须有上限。"""
    cache = SimpleTTLCache(ttl=60.0, enabled=True, max_entries=16)
    for i in range(2000):
        cache.set(f"key-{i}", i)
    assert len(cache._cache) == 16


def test_cache_max_entries_defaults_to_settings() -> None:
    cache = SimpleTTLCache(ttl=60.0, enabled=True)
    assert cache.max_entries == get_settings().route_cache_max_entries


def test_cache_is_thread_safe_under_concurrent_read_write() -> None:
    """同步 def 路由跑在 anyio 线程池里，同一个缓存实例会被多线程并发读写。"""
    cache = SimpleTTLCache(ttl=60.0, enabled=True, max_entries=32)
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker(worker_id: int) -> None:
        barrier.wait()
        try:
            for i in range(500):
                cache.set(f"w{worker_id}-{i}", i)
                cache.get(f"w{(worker_id + 1) % 8}-{i}")
                if i % 100 == 0:
                    cache.get(f"w{worker_id}-{i}")
        except BaseException as exc:  # noqa: BLE001 - 测试里要抓住任何异常
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, f"并发读写抛异常: {errors!r}"
    assert len(cache._cache) <= 32


def test_cache_clear_is_safe_while_other_threads_write() -> None:
    cache = SimpleTTLCache(ttl=60.0, enabled=True, max_entries=64)
    errors: list[BaseException] = []
    stop = threading.Event()

    def writer() -> None:
        try:
            i = 0
            while not stop.is_set():
                cache.set(f"k{i}", i)
                cache.get(f"k{i}")
                i += 1
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, daemon=True) for _ in range(4)]
    for thread in threads:
        thread.start()
    for _ in range(50):
        cache.clear()
    stop.set()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, f"clear 与并发写冲突: {errors!r}"
    cache.clear()
    assert not cache._cache


# ---------------------------------------------------------------------------
# 2. 连接池配置
# ---------------------------------------------------------------------------


def test_engine_uses_explicit_queue_pool_sizing() -> None:
    settings = get_settings()
    pool = db_session.engine.pool
    assert isinstance(pool, QueuePool), "文件型 SQLite 必须显式走 QueuePool"
    assert pool.size() == settings.db_pool_size
    assert pool._max_overflow == settings.db_max_overflow
    assert pool._timeout == pytest.approx(settings.db_pool_timeout)
    assert pool._recycle == settings.db_pool_recycle
    assert pool._pre_ping is True
    # 默认的 5 + 10 = 15 条连接是"点击几秒无反应"的头号机制，必须被抬高
    assert pool.size() + pool._max_overflow > 15


def test_sqlite_connect_args_allow_cross_thread_reuse() -> None:
    assert db_session._connect_args["check_same_thread"] is False
    assert db_session._connect_args["timeout"] == 30


def test_memory_sqlite_still_uses_static_pool(monkeypatch) -> None:
    """内存库每条连接都是新的空库，绝不能被 QueuePool 拆成多条连接。"""
    from sqlalchemy import create_engine, text

    for url in ("sqlite:///:memory:", "sqlite+pysqlite:///:memory:"):
        assert db_session._looks_like_memory_sqlite(url), url

    assert not db_session._looks_like_memory_sqlite(
        f"sqlite:///{Path('/tmp/whatever.db')}"
    )

    # StaticPool 语义验证：建表与查询必须落在同一条连接上
    engine = create_engine("sqlite:///:memory:", future=True, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER)"))
        conn.commit()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar() == 0
    engine.dispose()


def test_sqlite_pragmas_include_wal_autocheckpoint() -> None:
    settings = get_settings()
    with db_session.engine.connect() as conn:
        from sqlalchemy import text

        value = conn.execute(text("PRAGMA wal_autocheckpoint")).scalar()
    assert int(value) == settings.sqlite_wal_autocheckpoint_pages


def test_pragma_order_keeps_auto_vacuum_before_wal() -> None:
    """auto_vacuum 必须排在 journal_mode=WAL 之前，否则永久变成空操作。"""
    # 只看真正执行的 cursor.execute 行，跳过注释里出现的同名 pragma
    executed = [
        line.strip()
        for line in inspect.getsource(db_session.set_sqlite_pragma).splitlines()
        if line.strip().startswith("cursor.execute(")
    ]
    joined = "\n".join(executed)
    assert joined.index("auto_vacuum=INCREMENTAL") < joined.index("journal_mode=WAL")
    assert "wal_autocheckpoint" in joined


# ---------------------------------------------------------------------------
# 3. SSE：纯 asyncio、跨线程投递、有界队列
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


async def _drain(response, max_chunks: int | None = None) -> str:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        if max_chunks is not None and len(chunks) >= max_chunks:
            break
    return "".join(chunks)


def test_sse_loop_does_not_use_anyio_thread_pool(monkeypatch) -> None:
    """每条 SSE 连接曾常驻占用一个 anyio 线程池 token（默认仅 40 个，且与所有
    同步 def 路由共享）。这里既检查源码里不再出现该调用，也在运行期断言未被调用。"""
    # 模块已完全不再 import anyio —— 从根上不可能再占用线程池 token
    assert not hasattr(stream_route, "anyio"), "stream.py 不应再依赖 anyio 线程池"
    assert "asyncio.wait_for" in inspect.getsource(stream_route.stream_events)

    calls: list[object] = []
    real_run_sync = anyio.to_thread.run_sync

    async def _tracking_run_sync(func, *args, **kwargs):
        calls.append(func)
        return await real_run_sync(func, *args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", _tracking_run_sync)
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)

    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)

    async def _run() -> str:
        response = await stream_route.stream_events(_FakeRequest(), limit=2)
        return await _drain(response)

    body = asyncio.run(_run())

    assert body.count('"type":"stream.keepalive"') == 2
    assert calls == [], f"SSE 循环仍在调用 anyio.to_thread.run_sync: {calls!r}"


def test_sse_receives_event_published_from_another_thread(monkeypatch) -> None:
    """event_bus 的 handler 是被后台线程同步调用的，事件必须能跨线程送达 SSE 循环。"""
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 5.0)
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)

    subscribed = threading.Event()

    original_subscribe = bus.subscribe

    def _tracking_subscribe(event_name: str, handler) -> None:
        original_subscribe(event_name, handler)
        if len(bus._handlers.get("news.updated", [])) >= 1:
            subscribed.set()

    monkeypatch.setattr(bus, "subscribe", _tracking_subscribe)

    def _publish_from_worker_thread() -> None:
        assert subscribed.wait(5)
        assert threading.current_thread() is not threading.main_thread()
        bus.publish("news.created", {"id": 7, "title": "from-thread"})
        bus.publish("news.updated", {"id": 7, "updated_fields": ["sentiment_label"]})

    async def _run() -> str:
        response = await stream_route.stream_events(_FakeRequest(), limit=2)
        publisher = threading.Thread(target=_publish_from_worker_thread, daemon=True)
        publisher.start()
        body = await _drain(response)
        publisher.join(timeout=5)
        return body

    body = asyncio.run(_run())

    assert '"type":"news.created"' in body
    assert '"type":"news.updated"' in body
    assert '"payload":{"id":7,"title":"from-thread"}' in body


def test_sse_queue_is_bounded_and_never_blocks_publisher(monkeypatch) -> None:
    """慢客户端不得让队列无限堆积，更不得反压住发布线程。"""
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.05)
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)

    settings_stub = get_settings().model_copy(update={"stream_queue_maxsize": 5})
    monkeypatch.setattr(stream_route, "get_settings", lambda: settings_stub)

    publish_elapsed: list[float] = []
    flood_count = 500

    def _flood() -> None:
        begin = time.monotonic()
        for i in range(flood_count):
            bus.publish("news.created", {"id": i})
        publish_elapsed.append(time.monotonic() - begin)

    async def _run() -> list[str]:
        response = await stream_route.stream_events(_FakeRequest(), limit=None)
        agen = response.body_iterator
        # 先拿一条 keepalive：订阅在生成器体内建立，必须先把生成器跑起来
        first = await agen.__anext__()
        assert '"stream.keepalive"' in first

        publisher = threading.Thread(target=_flood, daemon=True)
        publisher.start()
        publisher.join(timeout=10)
        assert not publisher.is_alive(), "发布线程被 SSE 队列阻塞住了"
        # 让 call_soon_threadsafe 排队的回调全部落地
        await asyncio.sleep(0.2)

        chunks: list[str] = []
        for _ in range(30):
            chunk = await agen.__anext__()
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
            if '"stream.keepalive"' in chunks[-1]:
                break
        await agen.aclose()
        return chunks

    chunks = asyncio.run(_run())

    # 发布方绝不被反压：500 条事件应当近乎瞬时发完
    assert publish_elapsed and publish_elapsed[0] < 5.0
    events = [c for c in chunks if '"type":"news.created"' in c]
    # 队列上限 5：积压的 500 条里最多只能留下 5 条，其余被丢弃
    assert 0 < len(events) <= 5, f"队列未按 maxsize=5 截断: 收到 {len(events)} 条"
    assert '"stream.keepalive"' in chunks[-1], "积压排空后应回到 keepalive"


# ---------------------------------------------------------------------------
# 4. handler 生命周期（泄漏修复）
# ---------------------------------------------------------------------------


def _handler_count(bus: InMemoryEventBus) -> int:
    return sum(len(handlers) for handlers in bus._handlers.values())


def test_sse_unsubscribes_all_handlers_after_stream_completes(monkeypatch) -> None:
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)
    baseline = _handler_count(bus)

    async def _run() -> None:
        response = await stream_route.stream_events(_FakeRequest(), limit=2)
        await _drain(response)

    asyncio.run(_run())

    assert _handler_count(bus) == baseline


def test_sse_unsubscribes_when_generator_closed_midway(monkeypatch) -> None:
    """客户端中途断开 → 生成器被 aclose()，handler 也必须退订。"""
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)
    baseline = _handler_count(bus)

    async def _run() -> None:
        response = await stream_route.stream_events(_FakeRequest(), limit=None)
        agen = response.body_iterator
        await agen.__anext__()
        assert _handler_count(bus) == baseline + len(stream_route.STREAM_EVENT_NAMES)
        await agen.aclose()

    asyncio.run(_run())

    assert _handler_count(bus) == baseline


def test_sse_leaves_no_handler_when_response_body_never_iterated(monkeypatch) -> None:
    """回归：subscribe 曾发生在返回 StreamingResponse 之前，unsubscribe 只在生成器
    finally 里。响应体从未被迭代（客户端在 headers 后断开、中间件短路）时，handler
    会永久泄漏，其闭包 queue 无人消费 —— 无界堆积并拖慢此后每一次 publish。"""
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)
    baseline = _handler_count(bus)

    async def _run():
        response = await stream_route.stream_events(_FakeRequest(), limit=1)
        # 故意不迭代 body_iterator，直接丢弃
        return response

    response = asyncio.run(_run())
    assert response.media_type == "text/event-stream"
    assert _handler_count(bus) == baseline, "响应体未被迭代时不得残留任何订阅"

    # 并且此时 publish 不应触达任何残留 handler
    bus.publish("news.created", {"id": 1})
    assert bus.handler_error_count == 0


def test_sse_repeated_connections_do_not_accumulate_handlers(monkeypatch) -> None:
    monkeypatch.setattr(stream_route, "STREAM_KEEPALIVE_SECONDS", 0.01)
    bus = InMemoryEventBus()
    monkeypatch.setattr(stream_route, "get_event_bus", lambda: bus)
    baseline = _handler_count(bus)

    async def _one() -> None:
        response = await stream_route.stream_events(_FakeRequest(), limit=1)
        await _drain(response)

    for _ in range(20):
        asyncio.run(_one())

    assert _handler_count(bus) == baseline
    assert stream_route.get_active_stream_connection_count() == 0


def test_active_connection_counter_is_lock_protected() -> None:
    """裸 global 自增自减在多线程下会丢计数，这里断言存在锁且计数最终归零。"""
    assert isinstance(stream_route._active_connections_lock, threading.Lock().__class__)

    errors: list[BaseException] = []

    def bump() -> None:
        try:
            for _ in range(2000):
                stream_route._adjust_active_connections(1)
                stream_route._adjust_active_connections(-1)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    before = stream_route.get_active_stream_connection_count()
    threads = [threading.Thread(target=bump) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors
    assert stream_route.get_active_stream_connection_count() == before
