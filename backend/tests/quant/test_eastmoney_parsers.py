from datetime import date

from app.services.quant.market_data.eastmoney_fund_flow import parse_fund_flow_payload
from app.services.quant.market_data.eastmoney_history import parse_kline_payload, secid_for_symbol


def test_secid_maps_sh_and_sz() -> None:
    assert secid_for_symbol("600519.SH") == "1.600519"
    assert secid_for_symbol("300750.SZ") == "0.300750"


def test_parse_unadjusted_kline_fixture() -> None:
    payload = {
        "data": {
            "klines": [
                "2026-04-10,1800.00,1810.50,1820.00,1790.00,12345,2.1e9,1.2,0.5,10.5,0.42",
                "bad-row",
            ]
        }
    }
    bars = parse_kline_payload("600519.SH", payload)
    assert len(bars) == 1
    bar = bars[0]
    assert bar.trade_date == date(2026, 4, 10)
    assert bar.open == 1800.0
    assert bar.close == 1810.5
    assert bar.turnover_rate == 0.42


def test_parse_fund_flow_fixture() -> None:
    payload = {
        "data": {
            "klines": ["2026-04-10,1000000,400000,300000,200000,100000,1.2"]
        }
    }
    rows = parse_fund_flow_payload("600519.SH", payload)
    assert len(rows) == 1
    assert rows[0].main_net_inflow == 1_000_000
    assert rows[0].main_net_pct == 1.2
