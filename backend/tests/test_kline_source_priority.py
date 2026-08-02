"""K 线数据源优先级回归测试。

与行情报价路径（test_quote_source_priority.py）是**同一个根因**：Yahoo 对 A 股
当日日线的 ``Close`` 是 NaN（Open/High/Low/Volume 都有值），而 ``_download_history``
此前只在 yfinance **抛异常或返回空 frame** 时才降级腾讯——"非空但最新行不完整"
会被 ``if not frame.empty: return frame`` 直接放行，随后 ``_serialize_candles``
跳过含 NaN 的行，结果**日 K 图上今天这根蜡烛整根缺失**，而且和报价一样不会
触发任何降级。

因此 A股/港股 K 线同样以腾讯为主源，与报价路径保持一致，也保证"现价"与
"最后一根蜡烛"同源。
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from app.services.market_chart_service import MarketChartService


def _frame(rows: list[tuple[str, float, float, float, float | None, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Date": pd.to_datetime(d), "Open": o, "High": h, "Low": lo, "Close": c, "Volume": v}
            for d, o, h, lo, c, v in rows
        ]
    ).set_index("Date")


A_SHARE_FRAME = _frame(
    [
        ("2026-07-24", 199.11, 205.83, 196.98, 199.18, 72822591),
        ("2026-07-27", 199.11, 211.50, 188.88, 211.90, 82758019),
    ]
)

# yfinance 对 A 股当日行的真实形态：四价里只有 Close 是 NaN。
YF_NAN_TAIL_FRAME = _frame(
    [
        ("2026-07-24", 199.11, 205.83, 196.98, 199.18, 72822591),
        ("2026-07-27", 199.11, 211.50, 188.88, None, 82758019),
    ]
)


def test_a_share_kline_prefers_tencent() -> None:
    service = MarketChartService()

    with (
        patch.object(service, "_download_history_fallback", return_value=A_SHARE_FRAME) as tencent,
        patch("yfinance.download") as yf_download,
    ):
        frame = service._download_history("002384.SZ", period="1y", interval="1d")

    assert tencent.called
    assert not yf_download.called, "腾讯已返回数据，不应再打 yfinance"
    assert len(frame) == 2
    assert frame["Close"].iloc[-1] == 211.90


def test_hk_kline_prefers_tencent() -> None:
    service = MarketChartService()

    with (
        patch.object(service, "_download_history_fallback", return_value=A_SHARE_FRAME) as tencent,
        patch("yfinance.download") as yf_download,
    ):
        service._download_history("9988.HK", period="1y", interval="1d")

    assert tencent.called
    assert not yf_download.called


def test_us_kline_stays_on_yfinance() -> None:
    """美股腾讯 K线 接口不支持，主源必须仍是 yfinance。"""
    service = MarketChartService()

    with (
        patch("yfinance.download", return_value=A_SHARE_FRAME) as yf_download,
        patch.object(service, "_download_history_fallback", return_value=None) as tencent,
    ):
        frame = service._download_history("AAPL", period="1y", interval="1d")

    assert yf_download.called
    assert not tencent.called, "美股没有腾讯 K线，不该做无谓的降级请求"
    assert len(frame) == 2


def test_a_share_kline_falls_back_to_yfinance_when_tencent_fails() -> None:
    service = MarketChartService()

    with (
        patch.object(service, "_download_history_fallback", return_value=None),
        patch("yfinance.download", return_value=A_SHARE_FRAME) as yf_download,
    ):
        frame = service._download_history("002384.SZ", period="1y", interval="1d")

    assert yf_download.called
    assert len(frame) == 2


def test_yfinance_frame_with_nan_close_on_latest_row_triggers_fallback() -> None:
    """最新一根 Close 为 NaN 属于"不完整"，必须触发降级而不是直接返回。

    这是当日蜡烛消失的直接原因：非空 frame 被原样返回，
    _serialize_candles 再把含 NaN 的当日行跳过。
    """
    service = MarketChartService()

    # 走美股路径（主源 yfinance），确保断言的是"NaN 尾行触发降级"这一条，
    # 而不是"A股优先腾讯"那条。
    with (
        patch("yfinance.download", return_value=YF_NAN_TAIL_FRAME),
        patch.object(service, "_download_history_fallback", return_value=A_SHARE_FRAME) as fallback,
    ):
        frame = service._download_history("AAPL", period="1y", interval="1d")

    assert fallback.called, "最新行 Close 为 NaN 时必须尝试降级源"
    assert frame["Close"].iloc[-1] == 211.90


def test_nan_tail_is_kept_when_no_fallback_is_available() -> None:
    """降级源也拿不到时，仍返回 yfinance 的数据，不能把整条 K 线打成失败。"""
    service = MarketChartService()

    with (
        patch("yfinance.download", return_value=YF_NAN_TAIL_FRAME),
        patch.object(service, "_download_history_fallback", return_value=None),
    ):
        frame = service._download_history("AAPL", period="1y", interval="1d")

    assert len(frame) == 2


def test_today_candle_survives_end_to_end_for_a_share() -> None:
    """端到端：A 股当日蜡烛必须出现在序列化结果里。"""
    service = MarketChartService()

    with patch.object(service, "_download_history_fallback", return_value=A_SHARE_FRAME):
        frame = service._download_history("002384.SZ", period="1y", interval="1d")

    candles = service._serialize_candles(frame)
    assert len(candles) == 2
    assert candles[-1]["time"].startswith("2026-07-27")
    assert candles[-1]["close"] == 211.90


def _mock_tencent_response(tc_symbol: str, volume_raw: str):
    """构造腾讯 K线 接口的响应；行格式为 [日期, 开, 收, 高, 低, 量]。"""
    import io
    import json as _json
    from contextlib import contextmanager

    payload = {
        "data": {
            tc_symbol: {
                "qfqday": [["2026-07-27", "199.15", "211.90", "211.90", "188.88", volume_raw]]
            }
        }
    }

    @contextmanager
    def fake_urlopen(*_args, **_kwargs):
        yield io.BytesIO(_json.dumps(payload).encode("utf-8"))

    return fake_urlopen


def test_a_share_tencent_kline_volume_is_converted_from_hands_to_shares() -> None:
    """A 股腾讯 K线 的成交量单位是**手**，必须 ×100 才与 Yahoo/报价口径一致。

    实测比值精确为 100.00（002384.SZ：腾讯 827,580 手 vs Yahoo 82,758,019 股）。
    不换算的话，切源后 K 线上的成交量会整体缩小 100 倍。
    报价路径的 TencentQuoteProvider 早已做了同样的换算。
    """
    service = MarketChartService()

    with patch("urllib.request.urlopen", _mock_tencent_response("sz002384", "827580")):
        frame = service._download_history_fallback("002384.SZ", "6mo", "1d")

    assert frame is not None
    assert frame["Volume"].iloc[-1] == 82_758_000


def test_hk_tencent_kline_volume_is_left_as_is() -> None:
    """港股腾讯 K线 的成交量本就是**股**（实测比值 1.00），不能再 ×100。"""
    service = MarketChartService()

    with patch("urllib.request.urlopen", _mock_tencent_response("hk09988", "58415973")):
        frame = service._download_history_fallback("9988.HK", "6mo", "1d")

    assert frame is not None
    assert frame["Volume"].iloc[-1] == 58_415_973


def test_cache_key_is_versioned_so_source_switch_does_not_serve_stale_payload() -> None:
    """切换数据源后，旧口径的缓存不能继续命中。"""
    service = MarketChartService()
    key = service._build_cache_key("002384.SZ", "1d", "1y")
    assert "002384.SZ" in key
    # 键里需要带版本段，否则 Redis 里 Yahoo 口径的旧 payload 会被继续返回。
    assert ":v2:" in key or key.endswith(":v2")
