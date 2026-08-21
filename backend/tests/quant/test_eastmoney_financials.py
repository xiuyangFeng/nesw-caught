"""东财财务解析器：fixture 测试，不打真网（沿袭既有约定）。"""

from __future__ import annotations

import pytest
from datetime import date

from app.models.market_data import FinancialFact
from app.services.quant.market_data.eastmoney_financials import (
    parse_main_target,
    secid_for_symbol,
)

# 东财 datacenter RPT_F10_FINANCE_MAINFINADATA 响应的最小真实结构（字段名原样保留）
FIXTURE_PAYLOAD = {
    "result": {
        "pages": 2,
        "data": [
            {
                "SECUCODE": "600519.SH",
                "SECURITY_CODE": "600519",
                "SECURITY_NAME_ABBR": "贵州茅台",
                "REPORT_DATE": "2024-03-31 00:00:00",
                "NOTICE_DATE": "2024-04-30 00:00:00",
                "DJD_DPNP_YOY": 18.4,
                "DJD_TOI_YOY": 21.1,
                "ROEJQ": 9.66,
                "XSMLL": 92.12,
            },
            {
                "SECUCODE": "600519.SH",
                "SECURITY_CODE": "600519",
                "SECURITY_NAME_ABBR": "贵州茅台",
                "REPORT_DATE": "2023-12-31 00:00:00",
                "NOTICE_DATE": "2024-03-30 00:00:00",
                "DJD_DPNP_YOY": -2.3,
                "DJD_TOI_YOY": None,
                "ROEJQ": None,
                "XSMLL": None,
            },
            {
                "SECUCODE": "600519.SH",
                "SECURITY_CODE": "600519",
                "SECURITY_NAME_ABBR": "贵州茅台",
                "REPORT_DATE": "2024-06-30 00:00:00",
                "NOTICE_DATE": "2024-08-31 00:00:00",
                "DJD_DPNP_YOY": None,
                "DJD_TOI_YOY": None,
                "ROEJQ": None,
                "XSMLL": None,
            },
        ],
    }
}


def test_secid_for_symbol() -> None:
    assert secid_for_symbol("600519.SH") == "600519.SH"
    assert secid_for_symbol("000001.SZ") == "000001.SZ"


def test_parse_main_target_maps_metrics_and_pit_date() -> None:
    rows = parse_main_target("600519.SH", FIXTURE_PAYLOAD)
    assert len(rows) == 2  # 全 None 期被过滤
    q1_2024 = next(row for row in rows if row.period_end == date(2024, 3, 31))
    assert q1_2024.available_at == date(2024, 4, 30)
    assert q1_2024.metrics["net_profit_yoy"] == pytest.approx(0.184)  # 百分数 → 比值
    assert q1_2024.metrics["revenue_yoy"] == pytest.approx(0.211)
    assert q1_2024.metrics["roe"] == 9.66
    assert q1_2024.metrics["gross_margin"] == 92.12
    # 部分字段缺失的期照常解析可用字段
    q4_2023 = next(row for row in rows if row.period_end == date(2023, 12, 31))
    assert q4_2023.metrics == {"net_profit_yoy": -0.023}


def test_parse_main_target_returns_empty_for_null_result() -> None:
    assert parse_main_target("600519.SH", {"result": None}) == []
    assert parse_main_target("600519.SH", {"result": {"data": None}}) == []


def test_parse_main_target_rejects_malformed_payload() -> None:
    import pytest

    with pytest.raises(RuntimeError):
        parse_main_target("600519.SH", {"result": {"data": "not-a-list"}})
    with pytest.raises(RuntimeError):
        parse_main_target("600519.SH", "garbage")


def test_upsert_financial_facts_is_idempotent() -> None:
    from app.db.market_session import MarketSessionLocal
    from app.services.quant.market_data.backfill import upsert_financial_facts

    with MarketSessionLocal() as session:
        session.query(FinancialFact).delete()
        session.commit()
    rows = parse_main_target("600519.SH", FIXTURE_PAYLOAD)
    with MarketSessionLocal() as session:
        first = upsert_financial_facts(session, rows)
        second = upsert_financial_facts(session, rows)
        session.commit()
        assert first == second
        assert session.query(FinancialFact).count() == 5  # 4 + 1（部分字段期）
