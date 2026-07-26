"""财报 / 事件日历服务。

为自选股批量抓取即将到来的财报日与除息日。yfinance 的 calendar /
get_earnings_dates 调用较慢，故：

- 使用进程内 TTL 缓存（默认 6 小时，TTL 从 settings 读），按 provider_symbol
  缓存“原始事件列表”（只缓存事件类型 + 日期，days_until 每次读取时按当前时间
  重新计算，避免缓存过期日）；
- 可选写一份 JSON 快照到 backend/data/calendar_snapshot.json（best-effort，
  失败不影响主流程），便于进程重启后人工排查；
- 对单只 symbol 拉取失败优雅跳过并计数，绝不整体抛错。

对 yfinance 的调用统一走 ``_make_ticker``，测试通过 monkeypatch 该函数注入
假 Ticker，从而完全离线、不联网。
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.simple_cache import SimpleTTLCache
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.quote_provider import equivalent_symbol_candidates, normalize_symbol

logger = logging.getLogger(__name__)

# 进程内 TTL 缓存单例：跨请求 / 跨 CalendarService 实例复用（路由层每次请求都会
# new 一个 service）。key = provider_symbol，value = list[{"event_type", "date"}]。
_calendar_cache: SimpleTTLCache | None = None

# JSON 快照落盘路径（backend/data/ 已被 .gitignore 忽略，不会污染版本库）。
_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "calendar_snapshot.json"

# 冷启动（缓存全空）时整批拉取的墙钟上限。此前是逐 symbol 串行调用 yfinance，
# N 只自选股 = N 次串行网络，请求线程会被挂住数十秒；现在并发 + 整批封顶，
# 超时未返回的 symbol 计入 skipped，绝不拖住 /calendar 请求。
_CALENDAR_BATCH_TIMEOUT_SECONDS = 20.0


def _get_cache() -> SimpleTTLCache:
    global _calendar_cache
    if _calendar_cache is None:
        ttl = float(get_settings().calendar_cache_ttl_seconds)
        # 日历缓存与路由缓存无关，始终启用（否则无法达到“yfinance 慢调用只跑一次”
        # 的目的，测试也依赖缓存命中断言）。
        _calendar_cache = SimpleTTLCache(ttl=ttl, enabled=True)
    return _calendar_cache


def clear_calendar_cache() -> None:
    """清空进程内日历缓存（供测试隔离使用）。"""
    if _calendar_cache is not None:
        _calendar_cache.clear()


def _release_session(session: Session) -> None:
    """联网之前结束只读事务，把 SQLite 连接尽早还给其它请求/worker。

    调用方须先把需要的 ORM 字段取成普通值（rollback 会让本事务内加载的 ORM
    对象过期）。传入 Mock session 时静默忽略。
    """
    try:
        session.rollback()
    except Exception:  # pragma: no cover - 测试里可能传入 Mock session
        pass


def _make_ticker(provider_symbol: str) -> Any:
    """构造 yfinance Ticker。抽成独立函数是唯一的对外网络出口，便于测试打桩。"""
    import yfinance as yf  # 延迟导入，风格对齐 quote_provider

    return yf.Ticker(provider_symbol)


def _coerce_date(value: Any) -> date | None:
    """把 date / datetime / pandas.Timestamp / 字符串等宽松地转成 date。"""
    if value is None:
        return None
    # 过滤 NaN / NaT（它们不等于自身）。
    try:
        if value != value:  # noqa: PLR0124 - 故意用于 NaN/NaT 检测
            return None
    except Exception:
        pass
    # datetime 是 date 的子类，pandas.Timestamp 又是 datetime 子类，先判 datetime。
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # 兼容暴露 .date() 的对象（如某些时间戳包装）。
    date_attr = getattr(value, "date", None)
    if callable(date_attr):
        try:
            resolved = date_attr()
            if isinstance(resolved, datetime):
                return resolved.date()
            if isinstance(resolved, date):
                return resolved
        except Exception:
            pass
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None


def _as_date_list(value: Any) -> list[date]:
    """把单个或多个日期字段统一成 date 列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[date] = []
    for item in items:
        coerced = _coerce_date(item)
        if coerced is not None:
            result.append(coerced)
    return result


class CalendarService:
    def __init__(self, *, snapshot_enabled: bool = True) -> None:
        # 快照写入默认开启；测试可关闭以免留下磁盘产物。
        self.snapshot_enabled = snapshot_enabled

    # ------------------------------------------------------------------
    # 对外 API
    # ------------------------------------------------------------------
    def get_upcoming_events(self, session: Session, days: int = 30) -> dict:
        """返回所有自选股在未来 ``days`` 天内的事件 + 每只的最近财报摘要。"""
        repository = WatchlistRepository(session)
        items = repository.list_all()

        raw_by_symbol: dict[str, list[dict]] = {}
        display_by_symbol: dict[str, str | None] = {}
        skipped_count = 0

        # 阶段一：只读库，把归一化结果拍平成普通值。
        targets: list[tuple[str, str, str | None]] = []  # (symbol, provider_symbol, display_name)
        for item in items:
            try:
                normalized = normalize_symbol(item.symbol, item.market)
            except ValueError:
                skipped_count += 1
                continue
            targets.append((normalized.symbol, normalized.provider_symbol, item.display_name))

        # 释放只读事务后再联网，避免抓取期间一直占着 SQLite 连接。
        _release_session(session)

        # 阶段二：并发抓取（缓存命中的不会真的走网络）。
        events_by_provider = self._fetch_events_concurrently([provider for _, provider, _ in targets])

        for symbol, provider_symbol, display_name in targets:
            raw_events = events_by_provider.get(provider_symbol)
            if raw_events is None:
                skipped_count += 1
                continue

            # 用归一化后的 symbol 作为键，与 /market/watchlist 行情载荷的 symbol
            # 对齐，前端卡片角标才能按 row.symbol 命中。
            raw_by_symbol[symbol] = raw_events
            display_by_symbol[symbol] = display_name

        result = self._build_response(raw_by_symbol, display_by_symbol, days=days, skipped_count=skipped_count)
        self._maybe_write_snapshot(raw_by_symbol, display_by_symbol)
        return result

    def get_symbol_calendar(self, symbol: str, session: Session, days: int = 90) -> dict:
        """返回单只 symbol 的日历（symbol 不在自选股中也能查）。"""
        repository = WatchlistRepository(session)
        stored = None
        for candidate in equivalent_symbol_candidates(symbol):
            stored = repository.get_by_symbol(candidate)
            if stored is not None:
                break

        raw_symbol = symbol.upper()
        display_name = stored.display_name if stored is not None else None
        market = stored.market if stored is not None else None

        try:
            normalized = normalize_symbol(raw_symbol, market)
        except ValueError:
            return self._build_response({}, {}, days=days, skipped_count=1)

        # 联网前先释放只读事务。
        _release_session(session)
        raw_events = self._fetch_symbol_events(normalized.provider_symbol)
        if raw_events is None:
            return self._build_response({}, {}, days=days, skipped_count=1)

        return self._build_response(
            {normalized.symbol: raw_events},
            {normalized.symbol: display_name},
            days=days,
            skipped_count=0,
        )

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _fetch_events_concurrently(self, provider_symbols: list[str]) -> dict[str, list[dict] | None]:
        """并发抓取多只 symbol 的原始事件，返回 {provider_symbol: events | None}。

        - 命中 TTL 缓存的 symbol 直接返回，不占用线程；
        - 整批设墙钟上限，超时的 symbol 记为 None（调用方计入 skipped）。
        """
        results: dict[str, list[dict] | None] = {}
        pending: list[str] = []
        cache = _get_cache()
        for provider_symbol in dict.fromkeys(provider_symbols):
            cached = cache.get(provider_symbol)
            if cached is not None:
                results[provider_symbol] = cached
            else:
                pending.append(provider_symbol)

        if not pending:
            return results

        max_workers = max(1, int(getattr(get_settings(), "market_chart_max_workers", 8)))
        deadline = time.monotonic() + _CALENDAR_BATCH_TIMEOUT_SECONDS
        pool = ThreadPoolExecutor(max_workers=min(len(pending), max_workers))
        try:
            futures = [(symbol, pool.submit(self._fetch_symbol_events, symbol)) for symbol in pending]
            for provider_symbol, future in futures:
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    results[provider_symbol] = future.result(timeout=remaining)
                except FutureTimeoutError:
                    logger.warning("calendar fetch timed out for %s", provider_symbol)
                    results[provider_symbol] = None
                except Exception as exc:  # pragma: no cover - _fetch_symbol_events 已自行兜底
                    logger.warning("calendar fetch failed for %s: %s", provider_symbol, exc)
                    results[provider_symbol] = None
        finally:
            # 不能 wait=True，否则整批超时会被 shutdown 重新阻塞回去。
            pool.shutdown(wait=False, cancel_futures=True)
        return results

    def _fetch_symbol_events(self, provider_symbol: str) -> list[dict] | None:
        """取单只 symbol 的原始事件列表（命中缓存则不再调用 yfinance）。

        返回 None 表示抓取失败（调用方据此计入 skipped）。空列表表示抓取成功但
        无事件。
        """
        cache = _get_cache()
        cached = cache.get(provider_symbol)
        if cached is not None:
            return cached

        try:
            ticker = _make_ticker(provider_symbol)
            raw_events = self._extract_raw_events(ticker)
        except Exception as exc:  # pragma: no cover - 依赖 yfinance/网络的真实路径
            logger.warning("calendar fetch failed for %s: %s", provider_symbol, exc)
            return None

        cache.set(provider_symbol, raw_events)
        return raw_events

    def _extract_raw_events(self, ticker: Any) -> list[dict]:
        """从 Ticker 解析财报日 / 除息日，做好各版本结构的防御。"""
        events: list[dict] = []
        earnings_dates: set[date] = set()

        # 1) ticker.calendar：新版 yfinance 返回 dict，旧版可能返回 DataFrame。
        calendar = None
        try:
            calendar = ticker.calendar
        except Exception as exc:  # pragma: no cover - 真实 yfinance 行为
            logger.debug("ticker.calendar unavailable: %s", exc)

        calendar_dict = self._calendar_to_dict(calendar)
        if calendar_dict:
            for earnings_date in _as_date_list(calendar_dict.get("Earnings Date")):
                earnings_dates.add(earnings_date)
            for ex_div in _as_date_list(calendar_dict.get("Ex-Dividend Date")):
                events.append({"event_type": "ex_dividend", "date": ex_div})

        # 2) get_earnings_dates：作为财报日的补充来源（calendar 无财报时尤其重要）。
        try:
            earnings_df = ticker.get_earnings_dates(limit=12)
        except Exception as exc:  # pragma: no cover - 真实 yfinance 行为
            earnings_df = None
            logger.debug("get_earnings_dates unavailable: %s", exc)

        for index_value in self._iter_dataframe_index(earnings_df):
            coerced = _coerce_date(index_value)
            if coerced is not None:
                earnings_dates.add(coerced)

        for earnings_date in earnings_dates:
            events.append({"event_type": "earnings", "date": earnings_date})

        return events

    def _calendar_to_dict(self, calendar: Any) -> dict | None:
        """把 ticker.calendar 归一成 dict，兼容 dict / DataFrame 两种形态。"""
        if calendar is None:
            return None
        if isinstance(calendar, dict):
            return calendar
        # 旧版 DataFrame：尝试 to_dict()，失败则放弃（不抛错）。
        to_dict = getattr(calendar, "to_dict", None)
        if callable(to_dict):
            try:
                converted = to_dict()
                if isinstance(converted, dict):
                    return converted
            except Exception:
                return None
        return None

    def _iter_dataframe_index(self, frame: Any):
        """安全地迭代 DataFrame.index（或任何暴露 index 可迭代对象的东西）。"""
        if frame is None:
            return []
        # 空 DataFrame 优雅跳过。
        try:
            if getattr(frame, "empty", False):
                return []
        except Exception:
            pass
        index = getattr(frame, "index", None)
        if index is None:
            return []
        try:
            return list(index)
        except Exception:
            return []

    def _build_response(
        self,
        raw_by_symbol: dict[str, list[dict]],
        display_by_symbol: dict[str, str | None],
        *,
        days: int,
        skipped_count: int,
    ) -> dict:
        today = datetime.now(UTC).date()
        events: list[dict] = []
        summaries: list[dict] = []

        for symbol, raw_events in raw_by_symbol.items():
            display_name = display_by_symbol.get(symbol)
            future_earnings: list[tuple[int, date]] = []

            for raw in raw_events:
                event_date = raw.get("date")
                if not isinstance(event_date, date):
                    continue
                days_until = (event_date - today).days
                if days_until < 0:
                    # 仅关注即将到来的事件，过去的一律跳过。
                    continue
                if raw.get("event_type") == "earnings":
                    future_earnings.append((days_until, event_date))
                if days_until <= days:
                    events.append(
                        {
                            "symbol": symbol,
                            "display_name": display_name,
                            "event_type": raw.get("event_type"),
                            "date": event_date.isoformat(),
                            "days_until": days_until,
                        }
                    )

            # 每只 symbol 的最近未来财报（不受窗口限制，用于卡片角标倒计时）。
            next_earnings_date = None
            next_earnings_days_until = None
            if future_earnings:
                next_earnings_days_until, nearest_date = min(future_earnings, key=lambda pair: pair[0])
                next_earnings_date = nearest_date.isoformat()

            summaries.append(
                {
                    "symbol": symbol,
                    "display_name": display_name,
                    "next_earnings_date": next_earnings_date,
                    "next_earnings_days_until": next_earnings_days_until,
                }
            )

        events.sort(key=lambda evt: (evt["days_until"], evt["symbol"], evt["event_type"]))

        return {
            "days": days,
            "events": events,
            "summaries": summaries,
            "skipped_count": skipped_count,
            "generated_at": datetime.now(UTC),
        }

    def _maybe_write_snapshot(
        self,
        raw_by_symbol: dict[str, list[dict]],
        display_by_symbol: dict[str, str | None],
    ) -> None:
        """best-effort 写 JSON 快照，任何异常都吞掉，绝不影响主流程。"""
        if not self.snapshot_enabled:
            return
        try:
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "symbols": {
                    symbol: {
                        "display_name": display_by_symbol.get(symbol),
                        "events": [
                            {"event_type": raw.get("event_type"), "date": raw["date"].isoformat()}
                            for raw in raw_events
                            if isinstance(raw.get("date"), date)
                        ],
                    }
                    for symbol, raw_events in raw_by_symbol.items()
                },
            }
            _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - 磁盘/权限异常
            logger.debug("calendar snapshot write skipped: %s", exc)
