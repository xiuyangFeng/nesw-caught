"""A minimal in-process TTL cache used by read-heavy API routes.

Whether a cache instance is active is controlled explicitly via the
``enabled`` constructor flag (wired from Settings.route_cache_enabled),
never by runtime test-framework detection.

线程安全说明（2026-07-25 读路径重构）：
本项目几乎所有路由都是同步 ``def``，FastAPI 会把它们丢进 anyio 线程池并发执行，
因此同一个缓存实例会被多个线程同时读写。此前是裸 dict：
  - 无锁：``get`` 里的 "先判断在不在、再取值、再 del" 是复合操作，另一个线程
    在中间 del 掉同一个 key 就会抛 KeyError；
  - 无容量上限：feed-layout 的 key 由 4 个查询参数拼成，攻击者/爬虫可用任意
    URL 参数把它撑爆内存；
  - 无淘汰：过期条目只有被再次读到才会删，冷 key 永远留在内存里。
现在统一用一把 ``threading.Lock`` 保护全部状态，并用 ``OrderedDict`` 实现
容量上限 + LRU 淘汰。公开 API（get/set/clear/ttl/enabled）签名保持不变。

响应字节缓存（FIX-A，2026-07-25）：
``SimpleTTLCache`` 只解决了“别重复查库/重复算”，但读接口最贵的一段其实是
**把几百个 Pydantic 对象序列化成 JSON**（``jsonable_encoder`` + ``json.dumps``，
纯 CPU 且被 GIL 串行化）。缓存模型对象时这一段每次请求都要重做：实测 32 并发下
``/topics`` 串行 10ms → p50 2318ms。``JsonBytesTTLCache`` 缓存的是**已渲染好的
JSON 字节**，命中时直接返回 ``Response``（FastAPI 见到 ``Response`` 实例就会跳过
``response_model`` 的校验与序列化，直接把字节写出去），从而把这段 CPU 也省掉。
路由上的 ``response_model=`` 必须保留 —— OpenAPI schema 仍由它生成，前端契约不变。

实测（ab -k -c 32 -n 960，334 话题 / 222 新闻的库）：
    /topics          25ms → 8ms p50，1130 → 3701 rps
    /news?limit=200  450ms → 9ms p50，72 → 3097 rps
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, TypeAdapter

# 未显式指定 max_entries 时的兜底上限。构造函数默认值取 None，
# 表示"读全局 settings.route_cache_max_entries"，读不到才退回这个常量。
_FALLBACK_MAX_ENTRIES = 512


def _default_max_entries() -> int:
    try:
        from app.core.config import get_settings

        return int(get_settings().route_cache_max_entries)
    except Exception:  # pragma: no cover - 配置不可用时不应让缓存构造失败
        return _FALLBACK_MAX_ENTRIES


class SimpleTTLCache:
    def __init__(self, ttl: float = 10.0, enabled: bool = True, max_entries: int | None = None):
        self.ttl = ttl
        self.enabled = enabled
        # 每实例可自定义容量；默认取 settings.route_cache_max_entries。
        resolved = max_entries if max_entries is not None else _default_max_entries()
        self.max_entries = max(1, int(resolved))
        # OrderedDict 充当 LRU：命中/写入时 move_to_end，淘汰时 popitem(last=False)。
        self._cache: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        if not self.enabled:
            return None
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            val, expire = entry
            if time.time() < expire:
                # 命中即视为"最近使用"，挪到队尾以免被 LRU 误淘汰。
                self._cache.move_to_end(key)
                return val
            # 过期条目就地删除；用 pop(key, None) 而不是 del，避免与并发
            # 淘汰/clear 竞争时抛 KeyError。
            self._cache.pop(key, None)
        return None

    def set(self, key: Hashable, val: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._cache[key] = (val, time.time() + self.ttl)
            self._cache.move_to_end(key)
            # 超出容量时淘汰最久未使用的条目（队首）。while 而非 if：
            # max_entries 可能在运行时被调小。
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# JSON 响应的 media type。手工返回 Response 时必须显式带上，
# 否则 starlette 会退化成 text/plain。
JSON_MEDIA_TYPE = "application/json"


# 同构列表（如 list[TopicItemView]）的 TypeAdapter 缓存：构造 TypeAdapter 本身
# 要花毫秒级，绝不能每请求都建一个。dict 的读写在 CPython 里是原子的，无需加锁。
_LIST_ADAPTERS: dict[type, TypeAdapter] = {}


def _fast_json_bytes(payload: Any) -> bytes | None:
    """走 pydantic 的 Rust 序列化器直出 JSON 字节；形状不认识就返回 None。

    与 ``jsonable_encoder`` + ``json.dumps`` 的纯 Python 路径相比快约 10 倍
    （334 条话题：4.7ms → 0.4ms），且实测输出逐字节一致 —— 两边都是
    ``by_alias=True``、紧凑分隔符、非 ASCII 不转义。这条路径同时惠及
    **route_cache_enabled=false 的部署**：那种配置下每个请求都要渲染一次。

    唯一已知的边界差异：float 为 NaN/Inf 时，pydantic 输出 ``null``，而
    ``json.dumps(allow_nan=False)`` 会抛 ValueError（即改造前会 500）。
    脏数据下"返回 null"严格优于"整个接口 500"，故不做特殊处理。
    """
    if isinstance(payload, BaseModel):
        return payload.__pydantic_serializer__.to_json(payload, by_alias=True)
    if isinstance(payload, list) and payload:
        item_type = type(payload[0])
        if issubclass(item_type, BaseModel) and all(type(i) is item_type for i in payload):
            adapter = _LIST_ADAPTERS.get(item_type)
            if adapter is None:
                adapter = TypeAdapter(list[item_type])  # type: ignore[valid-type]
                _LIST_ADAPTERS[item_type] = adapter
            return adapter.dump_json(payload, by_alias=True)
    return None


def render_json_bytes(payload: Any) -> bytes:
    """把视图模型渲染成与 FastAPI 默认响应**逐字节一致**的 JSON。

    FastAPI（0.135）返回非 Response 对象时的链路是 ``serialize_response()``：
    先 ``response_field.validate(value)`` —— 按 response_model **重新校验一遍**
    整棵对象树（几百个模型对象，这才是大头），再 ``response_field.serialize_json()``
    走 pydantic Rust 核心直出 JSON 字节，最后包成 ``Response(media_type="application/json")``。
    handler 直接返回 ``Response`` 时，这两步整个被跳过 —— 这正是 FIX-A 省掉的开销。

    这里优先走 ``_fast_json_bytes()``（同一个 pydantic Rust 序列化器，参数
    ``by_alias=True`` 与 FastAPI 一致），认不出形状时
    回落到 ``jsonable_encoder`` + ``JSONResponse.render()`` —— 后者是语义基准：
    它会用 ``model_dump(mode="json", by_alias=True)`` 处理 datetime/Decimal/枚举，
    再复用 starlette 自己的 render，因此字段顺序、null 处理、datetime 格式、
    分隔符与改造前完全相同。两条路径的等价性由
    ``tests/test_response_cache.py::test_fast_path_matches_jsonable_encoder_path`` 锁住。

    （唯一被跳过的是 FastAPI 对返回值按 response_model 的**再校验**：本项目所有
    被缓存的路由，handler 的返回类型与 response_model 是同一个类，再校验是语义上的
    恒等操作。``tests/test_response_cache.py`` 对每个端点都做了字节等价性断言。）
    """
    fast = _fast_json_bytes(payload)
    if fast is not None:
        return fast
    return JSONResponse(content=jsonable_encoder(payload)).body


def json_bytes_response(body: bytes) -> Response:
    """把缓存里的字节原样吐回去，绕开 response_model 的校验与序列化。"""
    return Response(content=body, media_type=JSON_MEDIA_TYPE)


class JsonBytesTTLCache(SimpleTTLCache):
    """存 JSON 字节（而非模型对象）的 TTL 缓存。

    继承自 ``SimpleTTLCache``，完全复用其锁 / TTL / LRU 语义，
    ``get``/``set``/``clear``/``ttl``/``enabled`` 的签名与行为一律不变；
    只是额外提供两个便捷方法，让路由代码保持三行。
    """

    def cached_response(self, key: Hashable) -> Response | None:
        """命中则返回可直接 return 的 ``Response``，未命中返回 ``None``。"""
        body = self.get(key)
        if body is None:
            return None
        return json_bytes_response(body)

    def store(self, key: Hashable, payload: Any) -> Response:
        """渲染 → 入缓存 → 返回 ``Response``（miss 分支用）。

        注意：即使 ``enabled=False``（``set`` 会直接 no-op），这里依然要返回渲染好的
        Response，保证缓存开关不影响响应内容。
        """
        body = render_json_bytes(payload)
        self.set(key, body)
        return json_bytes_response(body)
