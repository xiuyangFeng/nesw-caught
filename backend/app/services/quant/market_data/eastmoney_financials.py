"""东财 datacenter 主要财务指标（RPT_F10_FINANCE_MAINFINADATA）解析器。

聚合接口无 SLA，解析保持防御性：字段缺失/改版显式报错，不静默吞掉。
单测一律用 fixture，不打真网（沿袭既有约定）。指标口径（东财字段原样保留）：
- net_profit_yoy  单季归母净利同比（DJD_DPNP_YOY，百分数 → 比值）
- revenue_yoy     单季营业总收入同比（DJD_TOI_YOY，百分数 → 比值）
- roe             加权净资产收益率（ROEJQ，百分数）
- gross_margin    销售毛利率（XSMLL，百分数）
available_at 取 NOTICE_DATE（披露日），供 point-in-time 截点判断。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services import http_pool

DATA_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DATA_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
DATA_TIMEOUT_SECONDS = 15.0
REPORT_NAME = "RPT_F10_FINANCE_MAINFINADATA"

# 东财字段名 → 内部 metric_key
FIELD_MAP = {
    "net_profit_yoy": "DJD_DPNP_YOY",
    "revenue_yoy": "DJD_TOI_YOY",
    "roe": "ROEJQ",
    "gross_margin": "XSMLL",
}


@dataclass(frozen=True)
class ParsedFinancialRow:
    symbol: str
    period_end: date
    metrics: dict[str, float]
    available_at: date | None
    document_id: str = ""


def secid_for_symbol(symbol: str) -> str:
    code, _, exchange = symbol.upper().partition(".")
    if exchange == "SZ":
        return f"{code}.SZ"
    return f"{code}.SH"


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_ratio(value: object) -> float | None:
    """东财同比/占比字段是百分数（如 -5.23），转成比值（-0.0523）。"""
    if not isinstance(value, (int, float)) or value != value:  # 排除 NaN
        return None
    return float(value) / 100.0


def parse_main_target(symbol: str, payload: object) -> list[ParsedFinancialRow]:
    if not isinstance(payload, dict):
        raise RuntimeError("eastmoney datacenter payload is not an object")
    result = payload.get("result")
    if result is None:
        return []
    data = result.get("data") if isinstance(result, dict) else None
    if data is None:
        return []
    if not isinstance(data, list):
        raise RuntimeError("eastmoney datacenter payload missing data list")
    rows: list[ParsedFinancialRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        period_end = _parse_date(item.get("REPORT_DATE"))
        if period_end is None:
            continue
        metrics: dict[str, float] = {}
        ratio_fields = {"net_profit_yoy", "revenue_yoy"}
        for key, field in FIELD_MAP.items():
            value = item.get(field)
            if value is None:
                continue
            if key in ratio_fields:
                converted = _to_ratio(value)
                if converted is not None:
                    metrics[key] = converted
            elif isinstance(value, (int, float)) and value == value:
                metrics[key] = float(value)
        if not metrics:
            # 该期无任何可引用指标（未披露/停更），跳过而非落 0 值。
            continue
        rows.append(
            ParsedFinancialRow(
                symbol=symbol.upper(),
                period_end=period_end,
                metrics=metrics,
                available_at=_parse_date(item.get("NOTICE_DATE")),
                document_id=str(item.get("SECURITY_CODE") or ""),
            )
        )
    return rows


def fetch_financials(symbol: str, *, client=None) -> list[ParsedFinancialRow]:
    http_client = client or http_pool.get_feed_client()
    params = {
        "reportName": REPORT_NAME,
        "columns": "ALL",
        "filter": f'(SECUCODE="{secid_for_symbol(symbol)}")',
        "pageNumber": "1",
        "pageSize": "20",
        "sortTypes": "-1",
        "sortColumns": "REPORT_DATE",
    }
    try:
        response = http_client.get(
            DATA_URL, params=params, headers=DATA_HEADERS, timeout=DATA_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"failed to fetch eastmoney financials for {symbol}: {exc}") from exc
    return parse_main_target(symbol, payload)
