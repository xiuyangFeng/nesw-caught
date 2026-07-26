from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd
from fastapi import HTTPException
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.quote_provider import equivalent_symbol_candidates, normalize_symbol

logger = logging.getLogger(__name__)

# sparklines 整批的墙钟上限。单个 yf.download 自身 timeout=10s，30 个标的串行
# 最坏 300s；改并发后再压一个整批上限，保证请求线程绝不会被外部数据源拖死。
_SPARKLINE_BATCH_TIMEOUT_SECONDS = 15.0


@dataclass(slots=True)
class _CacheEntry:
    expires_at: datetime
    payload_json: str


class MarketChartService:
    _cache: dict[str, _CacheEntry] = {}

    def __init__(self, redis_client: Redis | object | None = None) -> None:
        settings = get_settings()
        self._redis = redis_client
        self._redis_url = settings.redis_url
        self._redis_timeout_seconds = settings.event_bus_publish_timeout_seconds
        self._cache_prefix = "market:kline:"
        self._max_workers = max(1, int(getattr(settings, "market_chart_max_workers", 8)))

    def get_kline(self, symbol: str, interval: str, range_name: str, session: Session) -> dict:
        watchlist_item = self._require_watchlist_symbol(symbol, session)
        cache_key = self._build_cache_key(watchlist_item.symbol, interval, range_name)
        # TTL 内命中缓存直接返回,避免每次请求都走 yf.download(1-3s)。
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        try:
            payload = self._build_kline_payload(watchlist_item.symbol, watchlist_item.market, interval, range_name, session)
            self._set_cache(cache_key, payload, ttl_seconds=self._ttl_for_interval(interval))
            return payload
        except Exception:
            # 过期缓存仍可作 stale 兜底。
            stale = self._get_cache(cache_key, allow_stale=True)
            if stale is not None:
                stale["stale"] = True
                return stale
            raise

    def get_sparklines(self, symbols: list[str], session: Session) -> dict[str, dict[str, list[float]]]:
        if len(symbols) > 30:
            raise HTTPException(status_code=400, detail="too many symbols")

        # 阶段一：先把需要的 DB 数据一次性读完，再释放只读事务，避免在后面
        # 长达数秒的外部抓取期间一直占着 SQLite 连接。
        resolved: list[tuple[str, str]] = []  # (watchlist_symbol, provider_symbol)
        for symbol in symbols:
            try:
                watchlist_item = self._require_watchlist_symbol(symbol, session)
                normalized = normalize_symbol(watchlist_item.symbol, watchlist_item.market)
                resolved.append((watchlist_item.symbol, normalized.provider_symbol))
            except Exception:
                continue
        self._release_session(session)

        if not resolved:
            return {}

        # 阶段二：并发抓取 + 整批墙钟上限。超时的标的返回空序列（前端显示"暂无数据"），
        # 抓取失败的标的沿用旧行为直接省略。
        result: dict[str, dict[str, list[float]]] = {}
        deadline = time.monotonic() + _SPARKLINE_BATCH_TIMEOUT_SECONDS
        pool = ThreadPoolExecutor(max_workers=min(len(resolved), self._max_workers))
        try:
            futures = [
                (watchlist_symbol, pool.submit(self._load_sparkline_prices, provider_symbol))
                for watchlist_symbol, provider_symbol in resolved
            ]
            for watchlist_symbol, future in futures:
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    result[watchlist_symbol] = {"prices": future.result(timeout=remaining)}
                except FutureTimeoutError:
                    logger.warning("sparkline fetch timed out for %s", watchlist_symbol)
                    result[watchlist_symbol] = {"prices": []}
                except Exception:
                    continue
        finally:
            # 绝不 wait=True：否则整批超时会被 shutdown 重新阻塞回去。
            pool.shutdown(wait=False, cancel_futures=True)
        return result

    def _load_sparkline_prices(self, provider_symbol: str) -> list[float]:
        history = self._download_history(provider_symbol, period="3mo", interval="1d")
        return [float(value) for value in history["Close"].tail(30).dropna().tolist()]

    @staticmethod
    def _release_session(session: Session) -> None:
        """在发起外部网络请求前结束只读事务，把 SQLite 连接尽早还给其它请求/worker。

        调用方必须在此之前把需要的 ORM 字段取成普通 Python 值（rollback 会让
        本事务内加载的 ORM 对象过期）。
        """
        try:
            session.rollback()
        except Exception:  # pragma: no cover - 测试里可能传入 Mock session
            pass

    def _build_kline_payload(self, symbol: str, market: str, interval: str, range_name: str, session: Session) -> dict:
        normalized = normalize_symbol(symbol.upper(), market)
        # 先读库（并把 ORM 行拍平成 dict），再释放事务，最后才走网络。
        news_items = self._load_related_news(symbol, session)
        self._release_session(session)

        history = self._download_history(normalized.provider_symbol, period=range_name, interval=interval)
        candles = self._serialize_candles(history)
        indicator_frame = history.copy()

        close = indicator_frame["Close"]
        high = indicator_frame["High"]
        low = indicator_frame["Low"]

        indicators = {
            "ma5": self._serialize_line(close.rolling(5).mean()),
            "ma10": self._serialize_line(close.rolling(10).mean()),
            "ma20": self._serialize_line(close.rolling(20).mean()),
            "ma60": self._serialize_line(close.rolling(60).mean()),
            "macd": self._serialize_macd(close),
            "kdj": self._serialize_kdj(high, low, close),
            "bollinger": self._serialize_bollinger(close),
        }

        news_events = self._align_news_events(candles, news_items)
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "range": range_name,
            "stale": False,
            "candles": candles,
            "indicators": indicators,
            "news_events": news_events,
        }

    def _load_related_news(self, symbol: str, session: Session) -> list[dict]:
        """把相关新闻提前拍平成普通 dict，这样释放事务后仍可安全使用。

        _align_news_events 本身就同时支持 ORM 对象与 dict，这里只做形态归一。
        """
        rows = NewsMentionsRepository(session).list_related_news(symbol)
        items: list[dict] = []
        for row in rows:
            if isinstance(row, dict):
                items.append(row)
                continue
            items.append(
                {
                    "id": getattr(row, "id", None),
                    "title": getattr(row, "title", ""),
                    "sentiment_label": getattr(row, "sentiment_label", "unknown"),
                    "summary": getattr(row, "summary", None),
                    "published_at": getattr(row, "published_at", None),
                }
            )
        return items

    def _require_watchlist_symbol(self, symbol: str, session: Session):
        repository = WatchlistRepository(session)
        for candidate in equivalent_symbol_candidates(symbol):
            item = repository.get_by_symbol(candidate)
            if item is not None:
                return item
        raise HTTPException(status_code=404, detail="watchlist symbol not found")

    def _download_history(self, provider_symbol: str, period: str, interval: str) -> pd.DataFrame:
        import yfinance as yf

        frame = yf.download(
            provider_symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            timeout=10,
            multi_level_index=False,
        )
        frame = self._normalize_history_frame(frame)
        if frame.empty:
            raise RuntimeError(f"no kline data for {provider_symbol}")
        return frame

    def _normalize_history_frame(self, history: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(history.columns, pd.MultiIndex):
            return history

        normalized = history.copy()
        normalized.columns = normalized.columns.get_level_values(0)
        return normalized

    def _serialize_candles(self, history: pd.DataFrame) -> list[dict]:
        candles: list[dict] = []
        for index, row in history.iterrows():
            candles.append(
                {
                    "time": self._format_time(index),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": None if pd.isna(row.get("Volume")) else int(row["Volume"]),
                }
            )
        return candles

    def _serialize_line(self, series: pd.Series) -> list[dict]:
        points: list[dict] = []
        for index, value in series.dropna().items():
            points.append({"time": self._format_time(index), "value": float(value)})
        return points

    def _serialize_macd(self, close: pd.Series) -> list[dict]:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        histogram = dif - dea
        points: list[dict] = []
        for index in close.index:
            if pd.isna(dif.loc[index]) or pd.isna(dea.loc[index]) or pd.isna(histogram.loc[index]):
                continue
            points.append(
                {
                    "time": self._format_time(index),
                    "dif": float(dif.loc[index]),
                    "dea": float(dea.loc[index]),
                    "histogram": float(histogram.loc[index]),
                }
            )
        return points

    def _serialize_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series) -> list[dict]:
        low_n = low.rolling(9).min()
        high_n = high.rolling(9).max()
        rsv = ((close - low_n) / (high_n - low_n) * 100).fillna(0)
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        points: list[dict] = []
        for index in close.index:
            if pd.isna(k.loc[index]) or pd.isna(d.loc[index]) or pd.isna(j.loc[index]):
                continue
            points.append({"time": self._format_time(index), "k": float(k.loc[index]), "d": float(d.loc[index]), "j": float(j.loc[index])})
        return points

    def _serialize_bollinger(self, close: pd.Series) -> list[dict]:
        middle = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = middle + 2 * std
        lower = middle - 2 * std
        points: list[dict] = []
        for index in close.index:
            if pd.isna(upper.loc[index]) or pd.isna(middle.loc[index]) or pd.isna(lower.loc[index]):
                continue
            points.append(
                {
                    "time": self._format_time(index),
                    "upper": float(upper.loc[index]),
                    "middle": float(middle.loc[index]),
                    "lower": float(lower.loc[index]),
                }
            )
        return points

    def _align_news_events(self, candles: list[dict], news_items: list[object]) -> list[dict]:
        trading_days = sorted(candle["time"] for candle in candles)
        if not trading_days:
            return []

        grouped: dict[str, list[dict]] = {}
        for item in news_items:
            published_at = getattr(item, "published_at", None) if not isinstance(item, dict) else item.get("published_at")
            if not published_at:
                continue
            published_day = self._parse_day(published_at)
            anchor = self._find_anchor_day(trading_days, published_day)
            if anchor is None:
                continue
            grouped.setdefault(anchor, []).append(
                {
                    "id": int(getattr(item, "id", None) if not isinstance(item, dict) else item.get("id")),
                    "title": str(getattr(item, "title", "") if not isinstance(item, dict) else item.get("title", "")),
                    "sentiment": str(
                        getattr(item, "sentiment_label", "unknown") if not isinstance(item, dict) else item.get("sentiment_label", "unknown")
                    ),
                    "summary": str(getattr(item, "summary", "") or "" if not isinstance(item, dict) else (item.get("summary") or "")),
                }
            )

        return [{"time": day, "items": grouped[day]} for day in trading_days if day in grouped]

    def _find_anchor_day(self, trading_days: list[str], published_day: str) -> str | None:
        for day in reversed(trading_days):
            if day <= published_day:
                return day
        return None

    def _parse_day(self, value: str | datetime) -> str:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(UTC).date().isoformat()

    def _format_time(self, value) -> str:
        return pd.Timestamp(value).strftime("%Y-%m-%d")

    def _build_cache_key(self, symbol: str, interval: str, range_name: str) -> str:
        return f"{self._cache_prefix}{symbol.upper()}:{interval}:{range_name}"

    def _ttl_for_interval(self, interval: str) -> int:
        return 3600 if interval in {"1wk", "1mo"} else 300

    def _get_cache(self, cache_key: str, *, allow_stale: bool = False) -> dict | None:
        redis_client = self._get_redis_client()
        if redis_client is not None:
            try:
                cached_payload = redis_client.get(cache_key)
            except Exception:
                cached_payload = None
            if cached_payload:
                if isinstance(cached_payload, bytes):
                    cached_payload = cached_payload.decode("utf-8")
                return json.loads(cached_payload)

        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if entry.expires_at < datetime.now(UTC) and not allow_stale:
            return None
        return json.loads(entry.payload_json)

    def _set_cache(self, cache_key: str, payload: dict, ttl_seconds: int) -> None:
        payload_json = json.dumps(payload)
        redis_client = self._get_redis_client()
        if redis_client is not None:
            try:
                redis_client.set(cache_key, payload_json, ex=ttl_seconds)
            except Exception:
                pass
        self._cache[cache_key] = _CacheEntry(
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            payload_json=payload_json,
        )

    def _get_redis_client(self):
        if self._redis is not None:
            return self._redis
        try:
            self._redis = Redis.from_url(
                self._redis_url,
                socket_timeout=self._redis_timeout_seconds,
                decode_responses=True,
            )
        except Exception:
            self._redis = False
        return None if self._redis is False else self._redis
