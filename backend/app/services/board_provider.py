"""东方财富行业板块行情数据源。

设计文档：docs/superpowers/specs/2026-08-02-market-overview-design.md 五节。

- ``EastMoneyBoardProvider.fetch_industry_boards``：一次请求 push2 clist 接口
  返回行业板块整榜（m:90+t:2），防御性解析，结构异常抛 ``RuntimeError``
  （对齐腾讯 provider 的失败语义，由缓存层统一降级）。
- 模块级 TTL 进程内缓存（``threading.Lock`` + ``cached_at``，模式对齐
  ``QuoteService._hot_symbols_cache``）：``get_cached_industry_boards`` 供
  overview 读路径与 worker 刷新共用；抓取失败返回上一份缓存并标 ``stale``，
  无缓存则返回空列表 + ``status="fetch_failed"``，不向外抛异常。
- 板块榜单不落 ``price_snapshot``（一次 50 条、语义与逐 symbol 报价不同）。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.services import http_pool
from app.services.quote_provider import _coerce_float, _coerce_int

logger = logging.getLogger(__name__)

_BOARD_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_BOARD_LIST_PARAMS = {
    "pn": "1",
    "pz": "50",
    "po": "1",  # 降序（配合 fid=f3 = 按涨跌幅从高到低）
    "np": "1",
    "fltt": "2",
    "invt": "2",
    "fid": "f3",  # 按涨跌幅排序
    "fs": "m:90+t:2",  # 行业板块（t:3 为概念板块，本期不接）
    "fields": "f12,f14,f2,f3,f104,f105,f106,f62",
}
_BOARD_LIST_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
_BOARD_REQUEST_TIMEOUT_SECONDS = 5.0

# 板块进程内缓存 TTL（秒）。core/config.py 当前由并行任务独占，先放模块级，
# 后续可迁入 config 的 market_board_cache_ttl_seconds（默认同为 60s）。
MARKET_BOARD_CACHE_TTL_SECONDS = 60


@dataclass(slots=True)
class BoardQuote:
    """单个行业板块行情快照（字段映射见设计文档五节表格）。"""

    code: str  # f12 板块代码，如 BK0420
    name: str | None  # f14 板块名称
    price: float | None  # f2 板块指数点位
    change_percent: float | None  # f3 涨跌幅 %
    advance_count: int | None  # f104 板块内上涨家数
    decline_count: int | None  # f105 下跌家数
    flat_count: int | None  # f106 平盘家数
    net_inflow: float | None  # f62 主力净流入（元）
    fetched_at: datetime


@dataclass(slots=True)
class BoardFetchResult:
    """板块榜单缓存读取结果（供 MarketOverviewService 组装 payload）。

    - ``status``: "ok" / "fetch_failed"（仅无缓存且抓取失败时为后者）
    - ``stale``: True 表示本次抓取失败、返回的是上一份 TTL 已过期的缓存
    """

    status: str
    stale: bool
    items: list[BoardQuote] = field(default_factory=list)
    message: str | None = None
    fetched_at: datetime | None = None


class EastMoneyBoardProvider:
    """东财行业板块榜单 provider（非官方接口，无 SLA，解析保持防御性）。"""

    source_name = "eastmoney"

    def fetch_industry_boards(self, limit: int = 20) -> list[BoardQuote]:
        """抓取行业板块涨跌榜，按涨跌幅降序，最多返回 ``limit`` 条。

        HTTP 失败/限流或响应结构缺失（data/diff）时抛 ``RuntimeError``；
        单条目的数值字段缺失/类型异常容错为 None，缺 f12 代码的条目跳过。
        """
        try:
            client = http_pool.get_feed_client()
            response = client.get(
                _BOARD_LIST_URL,
                params=_BOARD_LIST_PARAMS,
                headers=_BOARD_LIST_HEADERS,
                timeout=_BOARD_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(f"failed to fetch eastmoney industry boards: {exc}") from exc

        return self._parse_boards(payload, limit=limit)

    @staticmethod
    def _parse_boards(payload: object, *, limit: int) -> list[BoardQuote]:
        data = payload.get("data") if isinstance(payload, dict) else None
        diff = data.get("diff") if isinstance(data, dict) else None
        # 个别东财接口版本 diff 为 dict（按序号 key），兼容取 values。
        if isinstance(diff, dict):
            diff = list(diff.values())
        if not isinstance(diff, list):
            # 结构级解析失败视为整体失败，不做部分字段猜测（设计文档五节）。
            raise RuntimeError("unexpected eastmoney clist payload: data.diff missing or invalid")

        fetched_at = datetime.now(UTC)
        boards: list[BoardQuote] = []
        for item in diff:
            if len(boards) >= limit:
                break
            if not isinstance(item, dict):
                continue
            code = item.get("f12")
            if not code or not isinstance(code, str):
                continue
            boards.append(
                BoardQuote(
                    code=code,
                    name=item.get("f14") if isinstance(item.get("f14"), str) else None,
                    price=_coerce_float(item.get("f2")),
                    change_percent=_coerce_float(item.get("f3")),
                    advance_count=_coerce_int(item.get("f104")),
                    decline_count=_coerce_int(item.get("f105")),
                    flat_count=_coerce_int(item.get("f106")),
                    net_inflow=_coerce_float(item.get("f62")),
                    fetched_at=fetched_at,
                )
            )
        return boards


_board_cache: BoardFetchResult | None = None
_board_cache_lock = threading.Lock()


def get_cached_industry_boards(
    limit: int = 20,
    *,
    ttl_seconds: float | None = None,
    provider: EastMoneyBoardProvider | None = None,
) -> BoardFetchResult:
    """读取板块榜单：TTL 内命中直接返回，过期/为空则同步抓取一次并刷新缓存。

    抓取失败：有旧缓存返回旧缓存 + ``stale=True``；无缓存返回空列表 +
    ``status="fetch_failed"``。该函数不向外抛异常（对齐零延迟保底思路）。
    """
    global _board_cache
    ttl = MARKET_BOARD_CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now = datetime.now(UTC)

    with _board_cache_lock:
        cached = _board_cache
    if cached is not None and cached.fetched_at is not None:
        if now - cached.fetched_at < timedelta(seconds=ttl):
            return BoardFetchResult(
                status="ok",
                stale=False,
                items=list(cached.items),
                message=None,
                fetched_at=cached.fetched_at,
            )

    fetcher = provider or EastMoneyBoardProvider()
    try:
        items = fetcher.fetch_industry_boards(limit=limit)
    except Exception as exc:
        logger.warning("eastmoney board fetch failed: %s", exc)
        if cached is not None:
            return BoardFetchResult(
                status="ok",
                stale=True,
                items=list(cached.items),
                message=str(exc),
                fetched_at=cached.fetched_at,
            )
        return BoardFetchResult(status="fetch_failed", stale=False, items=[], message=str(exc))

    result = BoardFetchResult(status="ok", stale=False, items=items, fetched_at=now)
    with _board_cache_lock:
        _board_cache = result
    return result


def clear_board_cache() -> None:
    """清空板块榜单缓存（主要用于测试）。"""
    global _board_cache
    with _board_cache_lock:
        _board_cache = None
