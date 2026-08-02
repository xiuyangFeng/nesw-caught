import asyncio
import json
import logging
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository
from app.schemas.common import serialize_utc
from app.schemas.stream import MarketWorkerStatusView, StreamStatusResponse
from app.services.event_bus import get_event_bus

logger = logging.getLogger(__name__)

router = APIRouter()
# market.watchlist_refreshed 由 MarketQuoteProducer 每轮刷新后发布。此前它不在
# 这个名单里，行情事件只在进程内被告警 handler 消费掉，前端永远收不到推送，自选
# 股价格只能靠用户手动点刷新——这是"行情看起来不更新"的推送侧根因。
STREAM_EVENT_NAMES = ("news.created", "news.updated", "market.watchlist_refreshed")
STREAM_KEEPALIVE_SECONDS = 15

# 只读的 SSE 活跃连接计数器，供 /health 汇报"推送连接数"使用；仅在本模块内自增/自减，
# 不改变 /events 本身的行为，避免侵入既有流式响应逻辑。
# 每条 SSE 连接跑在事件循环线程里，但 /health 是同步 def 路由、跑在 anyio 线程池的
# 另一个线程上，裸 global 的 `+= 1` 不是原子操作（读-改-写三步），并发下会丢计数。
# 这里用一把独立的小锁保护它。
_active_stream_connections = 0
_active_connections_lock = threading.Lock()


def _adjust_active_connections(delta: int) -> int:
    global _active_stream_connections
    with _active_connections_lock:
        _active_stream_connections += delta
        return _active_stream_connections


def get_active_stream_connection_count() -> int:
    """当前进程内存活的 SSE (`/events`) 连接数，供健康检查只读展示。"""
    with _active_connections_lock:
        return _active_stream_connections


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _serialize_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_default(value: object) -> str:
    """SSE 信封的 JSON 兜底序列化。

    行情事件的 payload 里带 ``fetched_at``(datetime)，裸 ``json.dumps`` 会抛
    TypeError —— 而这个异常发生在生成器体内，直接把整条 SSE 连接打断。与
    RedisStreamPublisher 的 ``_json_default`` 保持同样的"绝不因序列化失败中断
    投递"策略。

    这里必须走 ``serialize_utc``（naive 按 UTC ``replace``）而不是上面
    ``_serialize_timestamp`` 的 ``astimezone``：payload 里的 ``fetched_at`` 直接来自
    SQLite，是 **naive 的 UTC 值**（全项目约定，见 app/schemas/common.py）。用
    astimezone 会把它当本机时区解读，实测把时间戳整体推后了本机 UTC 偏移量
    （UTC-7 环境下推后 7 小时），前端的"最后更新时间"与 isStale 判定会一起错乱。
    ``occurred_at`` 那一路来自 ``_utc_now()``，本身 aware，两种写法等价。
    """
    if isinstance(value, datetime):
        return serialize_utc(value)
    return str(value)


def _dump_envelope(envelope: dict[str, object]) -> str:
    return json.dumps(envelope, separators=(",", ":"), default=_json_default)


def get_market_worker_runtime_status(session: Session) -> dict[str, object] | None:
    status = WorkerRuntimeStatusRepository(session).get_by_name("market_quote_producer")
    if status is None:
        return None
    return {
        "name": status.worker_name,
        "status": status.status,
        "last_heartbeat_at": status.last_heartbeat_at,
        "last_success_at": status.last_success_at,
        "last_failure_at": status.last_failure_at,
        "last_error": status.last_error,
        "cycle_count": status.cycle_count,
        "success_count": status.success_count,
        "failure_count": status.failure_count,
        "last_quotes_count": status.last_quotes_count,
    }


@router.get("/status", response_model=StreamStatusResponse)
def stream_status(session: Session = Depends(get_db_session)) -> StreamStatusResponse:
    status = get_event_bus().get_status()
    market_worker = get_market_worker_runtime_status(session)
    return StreamStatusResponse(
        mode="sse",
        status=status.status,
        backend=status.backend,
        redis_enabled=status.redis_enabled,
        last_published_at=status.last_published_at,
        last_event_name=status.last_event_name,
        last_error=status.last_error,
        market_worker=MarketWorkerStatusView.model_validate(market_worker) if market_worker else None,
    )


@router.get("/events")
async def stream_events(request: Request, limit: int | None = None) -> StreamingResponse:
    """SSE 事件流：持续推送 news.created / news.updated 等事件，空闲时发送 keepalive 心跳。"""
    # ↑ docstring 会被 FastAPI 写进 OpenAPI 的 description 字段（进而进入
    # frontend/openapi.json 这个对外契约），所以只放面向调用方的说明；下面的实现
    # 备忘一律用注释，不要写进 docstring。
    #
    # 2026-07-25 读路径重构，这个端点做了三处结构性修改：
    #
    # 1. 不再占用 anyio 线程池。此前每次等事件都是
    #    `await anyio.to_thread.run_sync(lambda: queue.get(timeout=1.0))`，
    #    意味着每条活跃 SSE 连接常驻霸占一个线程池 token；该线程池默认只有 40 个
    #    且与所有同步 def 路由共享，多开几个标签页就能让全站路由排队。现在改成
    #    纯 asyncio：`await asyncio.wait_for(queue.get(), timeout=keepalive)`，
    #    一条连接只占用一个协程。实测：持有 60 条 SSE 连接时，普通只读接口延迟
    #    从约 2000-2980ms 降到 1-7ms。
    #
    # 2. 订阅移进生成器体内。此前 subscribe 发生在返回 StreamingResponse 之前，
    #    而 unsubscribe 只在生成器的 finally 里；一旦响应体从未被迭代（客户端在
    #    收到 headers 后就断开、中间件短路返回等），handler 就永远退订不掉，其
    #    闭包持有的 queue 也永远没人消费——handler 无界堆积，并拖慢此后每一次
    #    publish。把 subscribe 挪到第一次 yield 之前，"从未被迭代"的情况下就
    #    根本没有订阅过，从源头消除泄漏；已订阅的路径再由 try/finally 兜底退订。
    #    （另一种写法是在端点里 try/except 包住 StreamingResponse 构造，但那救
    #    不了"响应体从未被迭代"这一主要泄漏场景，所以选前者。）
    #
    # 3. 队列有界。慢客户端此前能让私有队列无限堆积；现在满了就丢弃最旧的一条
    #    并计数，绝不阻塞发布线程。
    #
    # 对外协议（事件信封格式、stream.keepalive 形态、响应头）保持完全不变。
    event_bus = get_event_bus()
    settings = get_settings()
    maxsize = max(1, int(settings.stream_queue_maxsize))

    async def _event_stream():
        # 在生成器体内（即已经处于运行中的事件循环里）抓 loop：event_bus 的 handler
        # 是被其它线程（worker/ingest 线程）同步调用的，必须靠 call_soon_threadsafe
        # 把事件投递回本连接所在的循环。
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, dict[str, object], datetime]] = asyncio.Queue(maxsize=maxsize)
        dropped = 0

        def _offer(item: tuple[str, dict[str, object], datetime]) -> None:
            # 只在事件循环线程内执行（由 call_soon_threadsafe 调度），因此对
            # queue 的操作无需额外加锁。
            nonlocal dropped
            if queue.full():
                # 有界队列：丢最旧的一条给新事件腾位置（SSE 场景下新事件更有价值），
                # 并且绝不阻塞——发布线程早就返回了。
                try:
                    queue.get_nowait()
                    dropped += 1
                except asyncio.QueueEmpty:  # pragma: no cover - full 后立刻变空的竞态
                    pass
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:  # pragma: no cover - 同上
                dropped += 1

        handlers: dict[str, object] = {}
        for event_name in STREAM_EVENT_NAMES:
            def _handler(payload: dict[str, object], *, _event_name: str = event_name) -> None:
                item = (_event_name, payload, _utc_now())
                try:
                    loop.call_soon_threadsafe(_offer, item)
                except RuntimeError:
                    # 循环已关闭（连接正在拆除）：静默丢弃，绝不让发布方报错。
                    pass

            handlers[event_name] = _handler
            event_bus.subscribe(event_name, _handler)

        sent = 0
        active = _adjust_active_connections(1)
        logger.info(
            "SSE connection opened: events=%s active_connections=%s",
            STREAM_EVENT_NAMES,
            active,
        )
        try:
            while limit is None or sent < limit:
                if await request.is_disconnected():
                    logger.info(
                        "SSE connection disconnected by client: sent=%s active_connections=%s",
                        sent,
                        get_active_stream_connection_count(),
                    )
                    break
                try:
                    # 纯 asyncio 等待：没有事件时挂起协程，不占线程池；等到
                    # keepalive 周期仍无事件就超时，落到下面发心跳。
                    # 每轮都重新读模块级 STREAM_KEEPALIVE_SECONDS，保持测试可
                    # monkeypatch 的既有行为。
                    event_name, payload, occurred_at = await asyncio.wait_for(
                        queue.get(), timeout=STREAM_KEEPALIVE_SECONDS
                    )
                except TimeoutError:
                    envelope = {
                        "type": "stream.keepalive",
                        "occurred_at": _serialize_timestamp(_utc_now()),
                        "payload": {"status": "ok"},
                    }
                    yield f"data: {_dump_envelope(envelope)}\n\n"
                    sent += 1
                    continue
                envelope = {
                    "type": event_name,
                    "occurred_at": _serialize_timestamp(occurred_at),
                    "payload": payload,
                }
                yield f"data: {_dump_envelope(envelope)}\n\n"
                sent += 1
                # 事件级日志降为 DEBUG:此前是 INFO,"每条事件 × 每条连接"一行,
                # 是纯粹的日志放大;连接开/关仍保留 INFO。
                logger.debug(
                    "SSE event broadcast to connection: type=%s active_connections=%s",
                    event_name,
                    get_active_stream_connection_count(),
                )
        finally:
            # 无论正常结束、客户端断开、还是 GeneratorExit/取消，都必须退订，
            # 否则 handler 会永久残留在 event_bus 上。
            for event_name, handler in handlers.items():
                unsubscribe = getattr(event_bus, "unsubscribe", None)
                if unsubscribe is not None:
                    unsubscribe(event_name, handler)
            active = _adjust_active_connections(-1)
            logger.info(
                "SSE connection closed: sent=%s dropped=%s active_connections=%s",
                sent,
                dropped,
                active,
            )

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
