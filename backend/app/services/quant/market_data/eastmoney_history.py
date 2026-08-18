"""东财 push2his 不复权日线。聚合接口无 SLA，解析保持防御性。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.services import http_pool

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
KLINE_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
KLINE_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class ParsedDailyBar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    turnover_rate: float | None


def secid_for_symbol(symbol: str) -> str:
    code, _, exchange = symbol.upper().partition(".")
    if exchange == "SH":
        return f"1.{code}"
    return f"0.{code}"


def parse_kline_payload(symbol: str, payload: object) -> list[ParsedDailyBar]:
    if not isinstance(payload, dict):
        raise RuntimeError("eastmoney kline payload is not an object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("eastmoney kline payload missing data")
    klines = data.get("klines")
    if not isinstance(klines, list):
        raise RuntimeError("eastmoney kline payload missing klines")
    bars: list[ParsedDailyBar] = []
    for row in klines:
        if not isinstance(row, str):
            continue
        parts = row.split(",")
        if len(parts) < 7:
            continue
        try:
            trade_date = datetime.strptime(parts[0], "%Y-%m-%d").date()
            bars.append(
                ParsedDailyBar(
                    symbol=symbol.upper(),
                    trade_date=trade_date,
                    open=float(parts[1]),
                    close=float(parts[2]),
                    high=float(parts[3]),
                    low=float(parts[4]),
                    volume=float(parts[5]),
                    amount=float(parts[6]),
                    turnover_rate=float(parts[10]) if len(parts) > 10 and parts[10] not in {"", "-"} else None,
                )
            )
        except (TypeError, ValueError):
            continue
    return bars


def fetch_daily_bars(
    symbol: str,
    *,
    start: date,
    end: date,
    client=None,
) -> list[ParsedDailyBar]:
    http_client = client or http_pool.get_feed_client()
    params = {
        "secid": secid_for_symbol(symbol),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
    }
    try:
        response = http_client.get(
            KLINE_URL, params=params, headers=KLINE_HEADERS, timeout=KLINE_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"failed to fetch eastmoney kline for {symbol}: {exc}") from exc
    return parse_kline_payload(symbol, payload)
