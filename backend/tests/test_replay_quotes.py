"""历史行情样本回放测试。

覆盖 docs/stability-and-evolution.md 第 3 节"测试策略/回放测试"要求：保留一组历史行情
样本（港股 HKT、美股 ET 两种时区），用固定样本喂给现有的行情快照展示 schema
(`app.schemas.market.PriceSnapshotView`，其 `fetched_at: UTCDateTime` 字段复用
`app.schemas.common._normalize_utc` 作为解析入口)，断言不同时区表示的时间戳都被
正确归一化到 UTC，并验证跨市场排序/展示的正确性。

这些测试完全离线：样本文件是手工构造的历史快照 JSON，不发起任何真实网络请求（不调用
yfinance/腾讯行情接口）。未来行情数据源改版导致解析异常时，可以先跑本文件快速定位是
解析/归一化逻辑坏了还是数据源本身变了。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.market import PriceSnapshotView

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_snapshots(name: str) -> list[dict]:
    payload = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return payload["snapshots"]


def test_replay_hk_quote_snapshot_normalizes_hkt_offset_across_day_boundary() -> None:
    """港股快照：显式 +08:00(HKT) 偏移的 fetched_at 归一化到 UTC，覆盖跨日边界。"""
    rows = _load_snapshots("hk_quote_snapshot.json")
    views = [PriceSnapshotView(**row) for row in rows]

    assert len(views) == 2
    first, second = views

    assert first.symbol == "0700.HK"
    assert first.market == "hk"
    assert first.status == "ok"
    # 15:30 HKT (+08:00) -> 07:30 UTC，同一天。
    assert first.fetched_at == datetime(2025, 3, 17, 7, 30, tzinfo=UTC)

    assert second.status == "delayed"
    # 00:15 HKT 3/18 (+08:00) -> 16:15 UTC 3/17（跨日：本地次日凌晨对应 UTC 前一日傍晚）。
    assert second.fetched_at == datetime(2025, 3, 17, 16, 15, tzinfo=UTC)
    # second（3/18 00:15 HKT 采集）在真实时间上晚于 first（3/17 15:30 HKT 采集）。
    assert second.fetched_at > first.fetched_at


def test_replay_us_quote_snapshot_normalizes_et_offset_with_dst_transition() -> None:
    """美股快照：显式 ET 偏移（EST 与 EDT）的 fetched_at 归一化到 UTC，覆盖夏令时切换日与跨日边界。"""
    rows = _load_snapshots("us_quote_snapshot.json")
    views = [PriceSnapshotView(**row) for row in rows]

    assert len(views) == 2
    winter, summer = views

    assert winter.symbol == "AAPL"
    assert winter.market == "us"
    # 2025-03-09 是美国 DST 切换当天，01:30 EST(-05:00，切换前) -> 06:30 UTC。
    assert winter.fetched_at == datetime(2025, 3, 9, 6, 30, tzinfo=UTC)

    # 23:45 EDT(-04:00) 7/4 -> 03:45 UTC 7/5（跨日）。
    assert summer.fetched_at == datetime(2025, 7, 5, 3, 45, tzinfo=UTC)


def test_replay_cross_market_quote_snapshot_orders_correctly_after_utc_normalization() -> None:
    """混合快照：港股(+08:00)与美股(-04:00)不同时区表示下的同一真实时刻应归一化为相等的 UTC 值，
    且排序结果（按 fetched_at 降序，模拟 MarketRepository.list_latest 的展示顺序）符合预期。
    """
    rows = _load_snapshots("cross_market_quote_snapshot.json")
    views = {row["symbol"]: PriceSnapshotView(**row) for row in rows}

    hk_view = views["0700.HK"]
    aapl_view = views["AAPL"]
    tsla_view = views["TSLA"]

    # 20:00 HKT(+08:00) 5/1 与 08:00 EDT(-04:00) 5/1 是同一真实时刻。
    expected_common_instant = datetime(2025, 5, 1, 12, 0, tzinfo=UTC)
    assert hk_view.fetched_at == expected_common_instant
    assert aapl_view.fetched_at == expected_common_instant

    # TSLA 比前两条晚 5 分钟采集。
    assert tsla_view.fetched_at == datetime(2025, 5, 1, 12, 5, tzinfo=UTC)

    ordered = sorted(views.values(), key=lambda v: v.fetched_at, reverse=True)
    assert ordered[0].symbol == "TSLA"
    assert {ordered[1].symbol, ordered[2].symbol} == {"0700.HK", "AAPL"}
