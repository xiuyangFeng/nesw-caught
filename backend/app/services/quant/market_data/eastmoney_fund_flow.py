"""东财个股资金流日线。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.services import http_pool
from app.services.quant.market_data.eastmoney_history import secid_for_symbol

FFLOW_URL = "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"
FFLOW_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
FFLOW_TIMEOUT_SECONDS = 15.0


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


def _num(value: str) -> float | None:
    if value in {"", "-", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
                super_large_net=_num(parts[2]),
                large_net=_num(parts[3]),
                medium_net=_num(parts[4]),
                small_net=_num(parts[5]),
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
