"""A 股个股资金流：按需拉取东财日线资金流 + 进程内 TTL 缓存。

替代原量化模块的「回填进 market_data.db 再读库」链路：打开个股详情时现拉，
同一标的在 TTL 内只请求上游一次；上游失败返回空数据 + 说明，不抛 500，也不缓存失败结果。
东财对连续请求有限流（实测会返回空响应），TTL 缓存同时起到限流保护作用。

东财 ``fflow/daykline`` 每行字段顺序（实测确认：主力净流入 = 大单 + 超大单）::

    日期, 主力净流入, 小单净流入, 中单净流入, 大单净流入, 超大单净流入, 主力净占比, ...
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime

from app.core.config import get_settings
from app.schemas.market import FundFlowPointView, FundFlowView
from app.services import http_pool

logger = logging.getLogger(__name__)

# push2his 返回约 120 个交易日；push2 只返回当日一条（原量化回填即因此每只股只有 1 天）。
FFLOW_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
FFLOW_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
FFLOW_TIMEOUT_SECONDS = 15.0
A_SHARE_EXCHANGES = frozenset({"SH", "SZ", "BJ"})
DEFAULT_MAX_POINTS = 60

NOTE_NOT_A_SHARE = "资金流仅支持 A 股（沪深北）。"
NOTE_UPSTREAM_FAILED = "东财资金流暂时不可用，请稍后重试。"
NOTE_EMPTY = "东财暂无该股资金流数据。"


@dataclass(frozen=True)
class ParsedFundFlow:
    symbol: str
    trade_date: date
    main_net_inflow: float | None
    super_large_net: float | None
    large_net: float | None
    medium_net: float | None
    small_net: float | None
    main_net_pct: float | None


def _num(value: str | None) -> float | None:
    if value in {"", "-", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def secid_for_symbol(symbol: str) -> str:
    code, _, exchange = symbol.upper().partition(".")
    if exchange == "SH":
        return f"1.{code}"
    return f"0.{code}"


def is_a_share(symbol: str) -> bool:
    _, _, exchange = symbol.upper().partition(".")
    return exchange in A_SHARE_EXCHANGES


def parse_fund_flow_payload(symbol: str, payload: object) -> list[ParsedFundFlow]:
    if not isinstance(payload, dict):
        raise RuntimeError("eastmoney fund-flow payload is not an object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("eastmoney fund-flow payload missing data")
    klines = data.get("klines")
    if not isinstance(klines, list):
        raise RuntimeError("eastmoney fund-flow payload missing klines")
    rows: list[ParsedFundFlow] = []
    for raw in klines:
        if not isinstance(raw, str):
            continue
        parts = raw.split(",")
        if len(parts) < 6:
            continue
        try:
            trade_date = datetime.strptime(parts[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        rows.append(
            ParsedFundFlow(
                symbol=symbol.upper(),
                trade_date=trade_date,
                main_net_inflow=_num(parts[1]),
                small_net=_num(parts[2]),
                medium_net=_num(parts[3]),
                large_net=_num(parts[4]),
                super_large_net=_num(parts[5]),
                main_net_pct=_num(parts[6]) if len(parts) > 6 else None,
            )
        )
    return rows


def fetch_fund_flow(symbol: str, *, client=None) -> list[ParsedFundFlow]:
    http_client = client or http_pool.get_feed_client()
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": secid_for_symbol(symbol),
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
    }
    try:
        response = http_client.get(
            FFLOW_URL, params=params, headers=FFLOW_HEADERS, timeout=FFLOW_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"failed to fetch eastmoney fund-flow for {symbol}: {exc}") from exc
    return parse_fund_flow_payload(symbol, payload)


class FundFlowService:
    def __init__(
        self,
        *,
        client=None,
        ttl_seconds: float | None = None,
        max_points: int = DEFAULT_MAX_POINTS,
    ) -> None:
        self._client = client
        self._ttl_seconds = (
            float(get_settings().fund_flow_cache_ttl_seconds) if ttl_seconds is None else float(ttl_seconds)
        )
        self._max_points = max_points
        self._cache: dict[str, tuple[float, FundFlowView]] = {}
        self._lock = threading.Lock()

    def get_fund_flow(self, symbol: str) -> FundFlowView:
        normalized = symbol.strip().upper()
        if not is_a_share(normalized):
            return FundFlowView(symbol=normalized, points=[], note=NOTE_NOT_A_SHARE)

        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(normalized)
            if cached is not None and now - cached[0] < self._ttl_seconds:
                return cached[1]

        try:
            rows = fetch_fund_flow(normalized, client=self._client)
        except Exception as exc:
            logger.warning("fund flow fetch failed for %s: %s", normalized, exc)
            return FundFlowView(symbol=normalized, points=[], note=NOTE_UPSTREAM_FAILED)

        rows.sort(key=lambda row: row.trade_date)
        points = [
            FundFlowPointView(
                trade_date=row.trade_date,
                main_net_inflow=row.main_net_inflow,
                super_large_net=row.super_large_net,
                large_net=row.large_net,
                medium_net=row.medium_net,
                small_net=row.small_net,
                main_net_pct=row.main_net_pct,
            )
            for row in rows[-self._max_points :]
        ]
        view = FundFlowView(symbol=normalized, points=points, note=None if points else NOTE_EMPTY)
        with self._lock:
            self._cache[normalized] = (now, view)
        return view


_service: FundFlowService | None = None
_service_lock = threading.Lock()


def get_fund_flow_service() -> FundFlowService:
    global _service
    with _service_lock:
        if _service is None:
            _service = FundFlowService()
        return _service
