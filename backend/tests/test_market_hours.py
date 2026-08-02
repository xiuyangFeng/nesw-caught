"""market_hours 交易时段判断测试。

既有 is_market_open / any_market_open（cn/hk/us）语义为回归保护；
新增 _OVERVIEW_SESSIONS_UTC（kr/jp/eu）与 any_overview_market_open
对应设计文档八节「交易时段扩展」：

- kr：09:00-15:30 KST(UTC+9) → 00:00-06:30 UTC
- jp：09:00-15:00 JST(UTC+9) → 00:00-06:00 UTC（午休粗粒度忽略）
- eu：09:00-17:30 CET 粗粒度取 07:30-16:30 UTC
- cn/hk/us 复用现有时段；时段边界同样外扩 15 分钟；周末闭市。
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.market_hours import any_market_open, any_overview_market_open, is_market_open


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 回归：既有 cn/hk/us 语义不得因 overview 扩展而改变
# ---------------------------------------------------------------------------


def test_is_market_open_cn_sessions_and_margin() -> None:
    # 2026-08-04 是周二。A 股 01:30-03:30 / 05:00-07:00 UTC，边界外扩 15 分钟。
    assert is_market_open("cn", _utc(2026, 8, 4, 2, 0)) is True
    assert is_market_open("cn", _utc(2026, 8, 4, 1, 15)) is True  # 集合竞价外扩
    assert is_market_open("cn", _utc(2026, 8, 4, 4, 0)) is False  # 午间休市
    assert is_market_open("cn", _utc(2026, 8, 4, 6, 30)) is True


def test_is_market_open_us_and_hk() -> None:
    assert is_market_open("us", _utc(2026, 8, 4, 14, 0)) is True
    assert is_market_open("us", _utc(2026, 8, 4, 12, 0)) is False
    assert is_market_open("hk", _utc(2026, 8, 4, 3, 0)) is True
    assert is_market_open("hk", _utc(2026, 8, 4, 9, 0)) is False


def test_is_market_open_weekend_closed_and_unknown_market_open() -> None:
    # 2026-08-08 是周六。
    assert is_market_open("cn", _utc(2026, 8, 8, 2, 0)) is False
    assert is_market_open("us", _utc(2026, 8, 8, 14, 0)) is False
    # 未知市场按开市处理（宁可多刷新）——既有语义保持不变，kr/jp/eu 在
    # is_market_open 下依然走这个分支（overview 有自己的判断入口）。
    assert is_market_open("kr", _utc(2026, 8, 8, 2, 0)) is True
    assert is_market_open("unknown", _utc(2026, 8, 4, 12, 0)) is True


def test_any_market_open_only_considers_cn_hk_us() -> None:
    # 周二 10:00 UTC：cn/hk/us 均已闭市（cn 07:15 后、hk 08:15 后、us 未开盘），
    # 此时 eu 已开盘，但 any_market_open 不看 overview 市场。
    assert any_market_open(_utc(2026, 8, 4, 10, 0)) is False
    assert any_market_open(_utc(2026, 8, 4, 14, 0)) is True  # us 盘中


# ---------------------------------------------------------------------------
# 新增：any_overview_market_open（us/cn/kr/jp/eu）
# ---------------------------------------------------------------------------


def test_any_overview_market_open_kr_jp_session() -> None:
    # 周二 00:30 UTC：只有 kr(00:00-06:30)/jp(00:00-06:00) 在盘中
    # （cn/hk 要 01:15 外扩后才开，us 已闭市）——这是 overview 相对
    # any_market_open 新增的覆盖窗口。
    assert any_overview_market_open(_utc(2026, 8, 4, 0, 30)) is True
    assert any_market_open(_utc(2026, 8, 4, 0, 30)) is False
    # 周二 02:00 UTC：kr/jp/cn 均在盘中。
    assert any_overview_market_open(_utc(2026, 8, 4, 2, 0)) is True


def test_any_overview_market_open_eu_session() -> None:
    # 周二 10:00 UTC：eu(07:30-16:30) 盘中，此时 any_market_open 为 False。
    assert any_overview_market_open(_utc(2026, 8, 4, 10, 0)) is True
    assert any_overview_market_open(_utc(2026, 8, 4, 16, 45)) is True  # 外扩边界
    # cn 收盘外扩(07:15)与 eu 开盘外扩(07:15)正好相接，中间没有闭市空档。
    assert any_overview_market_open(_utc(2026, 8, 4, 7, 14)) is True  # cn 外扩边界内


def test_any_overview_market_open_us_session() -> None:
    assert any_overview_market_open(_utc(2026, 8, 4, 14, 0)) is True


def test_any_overview_market_open_all_closed_overnight() -> None:
    # 周三 22:30 UTC：us 收盘(21:15 后)、kr/jp 未开盘(23:45 前)，全部闭市。
    assert any_overview_market_open(_utc(2026, 8, 5, 22, 30)) is False


def test_any_overview_market_open_weekend_closed() -> None:
    # 周六全天闭市（即使落在 kr/jp UTC 时段内）。
    assert any_overview_market_open(_utc(2026, 8, 8, 2, 0)) is False
    assert any_overview_market_open(_utc(2026, 8, 8, 14, 0)) is False
    # 周日 23:50 UTC 虽接近 kr 周一开盘的外扩边界，但仍属周末。
    assert any_overview_market_open(_utc(2026, 8, 9, 23, 50)) is False
    # 时段判断不跨自然日回绕：周一 23:50 UTC 尚未进入 kr 周二 00:00 的开盘窗口
    # （start-margin 为负时不回绕到前一日），此时全部市场闭市。
    assert any_overview_market_open(_utc(2026, 8, 3, 23, 50)) is False
