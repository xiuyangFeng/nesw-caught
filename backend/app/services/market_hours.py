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


# ---------------------------------------------------------------------------
# 市场总览（Market Overview）专用时段表：在 cn/hk/us 之外扩展 kr/jp/eu。
# 刻意不动 _SESSIONS_UTC 与 is_market_open/any_market_open —— 它们服务于
# 自选股 producer 的降频判断，新增市场会改变其行为（例如盘中窗口变长）。
# ---------------------------------------------------------------------------
_OVERVIEW_SESSIONS_UTC: dict[str, tuple[tuple[time, time], ...]] = {
    "cn": _SESSIONS_UTC["cn"],
    "hk": _SESSIONS_UTC["hk"],
    "us": _SESSIONS_UTC["us"],
    # 韩国 09:00-15:30 KST(UTC+9) -> 00:00-06:30 UTC
    "kr": ((time(0, 0), time(6, 30)),),
    # 日本 09:00-15:00 JST(UTC+9) -> 00:00-06:00 UTC（午休粗粒度忽略）
    "jp": ((time(0, 0), time(6, 0)),),
    # 欧洲 09:00-17:30 CET 粗粒度取 07:30-16:30 UTC（覆盖伦敦 08:00-16:30
    # 与法兰克福，DST 取并集思路同美股）。
    "eu": ((time(7, 30), time(16, 30)),),
}


def _is_open_in_sessions(sessions: tuple[tuple[time, time], ...], moment: datetime) -> bool:
    """按给定时段表判断开市（含周末与边界外扩），与 is_market_open 同规则。"""
    moment = moment.astimezone(UTC)
    if moment.weekday() >= 5:
        return False
    current = _minutes(moment.timetz().replace(tzinfo=None))
    return any(
        _minutes(start) - _EDGE_MARGIN_MINUTES <= current <= _minutes(end) + _EDGE_MARGIN_MINUTES
        for start, end in sessions
    )


def is_overview_market_open(market: str, now: datetime | None = None) -> bool:
    """overview 覆盖市场（us/cn/hk/kr/jp/eu）单市场开市判断。

    与 is_market_open 的关键差异：未知市场返回 False 而不是 True——
    overview 的市场集合是封闭的，未知 key 属于调用方 bug，按闭市处理
    不会让任何标的静止（overview 只消费这张表里的市场）。
    """
    sessions = _OVERVIEW_SESSIONS_UTC.get((market or "").lower())
    if not sessions:
        return False
    return _is_open_in_sessions(sessions, now or datetime.now(UTC))


def any_overview_market_open(now: datetime | None = None) -> bool:
    """us/cn/hk/kr/jp/eu 中是否至少有一个处于交易时段（overview worker 降频用）。"""
    moment = now or datetime.now(UTC)
    return any(
        _is_open_in_sessions(sessions, moment) for sessions in _OVERVIEW_SESSIONS_UTC.values()
    )
