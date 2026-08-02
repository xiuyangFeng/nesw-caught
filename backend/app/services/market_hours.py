"""交易时段判断。

只服务于"行情轮询要不要降频"这一个用途，因此刻意保持粗粒度：
- 只按常规连续竞价时段 + 周末判断，不接节假日日历（错判的代价仅仅是闭市时多轮询
  几次，而不是漏掉盘中行情）；
- 时段边界各外扩 ``_EDGE_MARGIN_MINUTES``，保证集合竞价/收盘集合竞价期间仍按盘中
  频率刷新。

刻意不用 zoneinfo 的 DST 换算做美股夏令时精确切换：美东夏令时/冬令时的开盘对应
UTC 13:30 / 14:30，这里直接取两者的并集（13:30-21:00 UTC），宁可多开一小时也不
少开。
"""

from __future__ import annotations

from datetime import UTC, datetime, time

# 时段边界外扩的分钟数：覆盖集合竞价与开盘前最后一次报价刷新。
_EDGE_MARGIN_MINUTES = 15

# {market: ((start_utc, end_utc), ...)}，均为 UTC 墙钟时间。
_SESSIONS_UTC: dict[str, tuple[tuple[time, time], ...]] = {
    # A 股 09:30-11:30 / 13:00-15:00 CST(UTC+8) -> 01:30-03:30 / 05:00-07:00 UTC
    "cn": ((time(1, 30), time(3, 30)), (time(5, 0), time(7, 0))),
    # 港股 09:30-12:00 / 13:00-16:00 HKT(UTC+8) -> 01:30-04:00 / 05:00-08:00 UTC
    "hk": ((time(1, 30), time(4, 0)), (time(5, 0), time(8, 0))),
    # 美股 09:30-16:00 ET，夏令时 13:30-20:00 UTC、冬令时 14:30-21:00 UTC，取并集。
    "us": ((time(13, 30), time(21, 0)),),
}


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def is_market_open(market: str, now: datetime | None = None) -> bool:
    """粗粒度判断某个市场当前是否处于交易时段（不含节假日）。"""
    sessions = _SESSIONS_UTC.get((market or "").lower())
    if not sessions:
        # 未知市场按"开市"处理：宁可多刷新，也不要让某个标的静止不动。
        return True

    moment = (now or datetime.now(UTC)).astimezone(UTC)
    # 周末休市。A股/港股用 UTC 星期几判断没有偏差（其 UTC 时段仍落在同一自然日）；
    # 美股 UTC 时段同样不跨日，因此这里直接用 UTC weekday。
    if moment.weekday() >= 5:
        return False

    current = _minutes(moment.timetz().replace(tzinfo=None))
    return any(
        _minutes(start) - _EDGE_MARGIN_MINUTES <= current <= _minutes(end) + _EDGE_MARGIN_MINUTES
        for start, end in sessions
    )


def any_market_open(now: datetime | None = None) -> bool:
    """A股/港股/美股中是否至少有一个处于交易时段。"""
    moment = now or datetime.now(UTC)
    return any(is_market_open(market, moment) for market in _SESSIONS_UTC)
