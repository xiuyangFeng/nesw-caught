from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.services.ingestion.types import LATENCY_EMA_ALPHA

_ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
_US_EASTERN = ZoneInfo("America/New_York")
_UTC_ZONE = ZoneInfo("UTC")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ema_latency(previous: float | None, latest: float) -> float:
    if previous is None:
        return latest
    return round(LATENCY_EMA_ALPHA * latest + (1 - LATENCY_EMA_ALPHA) * previous, 2)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _default_feed_tz(market: str | None) -> ZoneInfo:
    """Naive feed timestamps: cn/hk→Shanghai, us→Eastern, else UTC."""
    key = (market or "").strip().lower()
    if key in {"cn", "hk"}:
        return _ASIA_SHANGHAI
    if key == "us":
        return _US_EASTERN
    return _UTC_ZONE


def _normalize_feed_datetime(value: datetime | None, *, market: str | None = None) -> datetime | None:
    """Normalize feed timestamps to UTC; naive values use market-local default TZ."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=_default_feed_tz(market))
    return value.astimezone(UTC)


# ---------------------------------------------------------------------------
# 中文相对时间 / 口语化时间解析
#
# 背景：36Kr、财联社、见闻等中文源在列表页只给「刚刚 / 5分钟前 / 昨天 09:15 / 07-25 10:00」
# 这类文本。旧实现只走 RFC2822 与 ISO8601 两条分支，中文文本一律解析失败并静默返回
# None —— published_at 为空的新闻不参与去重（dedup_gate 的签名与窗口都要求 published_at
# 非空），effective_at 也退化成 fetched_at，直接损伤时效性与去重质量。
# ---------------------------------------------------------------------------

# 「刚刚」「刚才」等：视为当前时刻
_CN_JUST_NOW = {"刚刚", "刚才", "现在", "just now"}

# 相对时间单位 → timedelta 参数；「个月」按 30 天近似（列表页极少出现，仅作兜底）
_CN_RELATIVE_UNITS: dict[str, timedelta] = {
    "秒": timedelta(seconds=1),
    "秒钟": timedelta(seconds=1),
    "分": timedelta(minutes=1),
    "分钟": timedelta(minutes=1),
    "小时": timedelta(hours=1),
    "个小时": timedelta(hours=1),
    "时": timedelta(hours=1),
    "天": timedelta(days=1),
    "日": timedelta(days=1),
    "周": timedelta(weeks=1),
    "星期": timedelta(weeks=1),
    "个星期": timedelta(weeks=1),
    "月": timedelta(days=30),
    "个月": timedelta(days=30),
}

# N秒前 / N分钟前 / N小时前 / N天前 ...（「前」亦允许写成「之前」）
_CN_RELATIVE_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>秒钟|秒|分钟|分|个小时|小时|时|天|日|个星期|星期|周|个月|月)\s*(?:之)?前$"
)

# 今天/昨天/前天 + 时钟
_CN_DAY_OFFSETS = {
    "今天": 0,
    "今日": 0,
    "昨天": -1,
    "昨日": -1,
    "前天": -2,
    "前日": -2,
}
_CN_DAY_CLOCK_RE = re.compile(
    r"^(?P<day>今天|今日|昨天|昨日|前天|前日)\s*"
    r"(?:(?P<hour>\d{1,2})[:：时点](?P<minute>\d{1,2})(?:[:：分](?P<second>\d{1,2}))?秒?)?$"
)

# 07-25 10:00 / 7月25日 10:00（无年份，需按参考时间补年）
_CN_MONTH_DAY_RE = re.compile(
    r"^(?P<month>\d{1,2})\s*[-/月.]\s*(?P<day>\d{1,2})\s*日?"
    r"(?:\s+(?P<hour>\d{1,2})[:：时点](?P<minute>\d{1,2})(?:[:：分](?P<second>\d{1,2}))?秒?)?$"
)

# 2026-07-25 10:00:00 / 2026年7月25日 10:00
_CN_FULL_RE = re.compile(
    r"^(?P<year>\d{4})\s*[-/年.]\s*(?P<month>\d{1,2})\s*[-/月.]\s*(?P<day>\d{1,2})\s*日?"
    r"(?:[\sT]+(?P<hour>\d{1,2})[:：时点](?P<minute>\d{1,2})(?:[:：分](?P<second>\d{1,2}))?秒?)?$"
)

# 裸时钟 15:03:13 / 15:03（财联社快讯列表页只给时分秒）
_CLOCK_ONLY_RE = re.compile(r"^(?P<hour>\d{1,2})[:：](?P<minute>\d{2})(?:[:：](?P<second>\d{2}))?$")

# 裸时钟拼日期时的容忍窗口：拼出来比参考时间晚超过这个跨度，判定为「昨天的条目」。
_CLOCK_FUTURE_TOLERANCE = timedelta(hours=2)


def _chinese_local_tz(market: str | None) -> ZoneInfo:
    """中文口语时间的参考时区：us 源用美东，其余（含未标注）一律按北京时间。

    与 `_default_feed_tz` 的差别在于兜底值——中文文本默认来自中国站点，
    兜底成 UTC 会平白引入 8 小时误差。
    """
    if (market or "").strip().lower() == "us":
        return _US_EASTERN
    return _ASIA_SHANGHAI


def _local_now(market: str | None, now: datetime | None) -> datetime:
    """把参考时间（默认当前时刻）转换到 market 对应的本地时区。"""
    reference = now or _utc_now()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return reference.astimezone(_chinese_local_tz(market))


def _clock_parts(match: re.Match[str]) -> tuple[int, int, int]:
    groups = match.groupdict()
    hour = int(groups.get("hour") or 0)
    minute = int(groups.get("minute") or 0)
    second = int(groups.get("second") or 0)
    return hour, minute, second


def _parse_chinese_datetime(
    raw: str | None,
    *,
    market: str | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """解析中文相对/口语时间文本，返回 UTC datetime；无法识别时返回 None。

    支持：刚刚、N秒前、N分钟前、N小时前、N天前、今天 HH:MM、昨天 HH:MM、
    前天 HH:MM、MM-DD HH:MM、YYYY-MM-DD HH:MM:SS（含中文年月日写法）。

    `now` 用于注入固定参考时间，便于测试；`market` 决定参考时区。
    """
    if not raw:
        return None

    text = str(raw).strip()
    if not text:
        return None
    # 归一化全角空格与「更新于/发布于」这类前缀
    text = text.replace("　", " ").replace("发布于", "").replace("更新于", "").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return None

    local_now = _local_now(market, now)
    tz = local_now.tzinfo

    if text.lower() in _CN_JUST_NOW:
        return local_now.astimezone(UTC).replace(microsecond=0)

    relative = _CN_RELATIVE_RE.match(text)
    if relative:
        unit = _CN_RELATIVE_UNITS.get(relative.group("unit"))
        if unit is not None:
            try:
                amount = float(relative.group("num"))
            except ValueError:
                return None
            return (local_now - unit * amount).astimezone(UTC).replace(microsecond=0)

    day_clock = _CN_DAY_CLOCK_RE.match(text)
    if day_clock:
        offset = _CN_DAY_OFFSETS[day_clock.group("day")]
        hour, minute, second = _clock_parts(day_clock)
        target_date = (local_now + timedelta(days=offset)).date()
        try:
            local_dt = datetime(
                target_date.year, target_date.month, target_date.day, hour, minute, second, tzinfo=tz
            )
        except ValueError:
            return None
        return local_dt.astimezone(UTC)

    full = _CN_FULL_RE.match(text)
    if full:
        hour, minute, second = _clock_parts(full)
        try:
            local_dt = datetime(
                int(full.group("year")),
                int(full.group("month")),
                int(full.group("day")),
                hour,
                minute,
                second,
                tzinfo=tz,
            )
        except ValueError:
            return None
        return local_dt.astimezone(UTC)

    month_day = _CN_MONTH_DAY_RE.match(text)
    if month_day:
        hour, minute, second = _clock_parts(month_day)
        month = int(month_day.group("month"))
        day = int(month_day.group("day"))
        for year in (local_now.year, local_now.year - 1):
            try:
                local_dt = datetime(year, month, day, hour, minute, second, tzinfo=tz)
            except ValueError:
                continue
            # 无年份的 MM-DD：若落在参考时间「未来一天以上」，说明是去年的条目
            if local_dt - local_now <= timedelta(days=1):
                return local_dt.astimezone(UTC)
        return None

    return None


def _parse_feed_datetime(
    raw: str | None,
    *,
    market: str | None = None,
    now: datetime | None = None,
) -> datetime | None:
    if not raw:
        return None

    try:
        return _normalize_feed_datetime(parsedate_to_datetime(raw), market=market)
    except (TypeError, ValueError):
        pass

    normalized = raw.replace("Z", "+00:00")
    try:
        return _normalize_feed_datetime(datetime.fromisoformat(normalized), market=market)
    except ValueError:
        pass

    # 兜底：中文相对/口语时间（刚刚、5分钟前、昨天 09:15 ...）
    return _parse_chinese_datetime(raw, market=market, now=now)


def _parse_list_time_text(
    raw: str | None,
    *,
    market: str | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """解析列表页时间栏文本，覆盖裸时钟（15:03:13）与中文口语时间。

    裸时钟按 **market 本地时区的当天日期** 补齐（旧实现用 UTC 当天日期却硬编码 +08:00，
    北京时间 00:00-08:00 的快讯会整整早 24 小时）。若补出来的时刻明显晚于参考时间，
    说明该条其实属于昨天，回退一天。
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None

    chinese = _parse_chinese_datetime(text, market=market, now=now)
    if chinese is not None:
        return chinese

    clock = _CLOCK_ONLY_RE.match(text)
    if clock:
        local_now = _local_now(market, now)
        hour, minute, second = _clock_parts(clock)
        try:
            local_dt = datetime(
                local_now.year, local_now.month, local_now.day, hour, minute, second, tzinfo=local_now.tzinfo
            )
        except ValueError:
            return None
        if local_dt - local_now > _CLOCK_FUTURE_TOLERANCE:
            local_dt -= timedelta(days=1)
        return local_dt.astimezone(UTC)

    return _parse_feed_datetime(text, market=market, now=now)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


def _canonicalize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, url.strip())
