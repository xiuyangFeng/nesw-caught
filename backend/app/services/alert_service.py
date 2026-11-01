"""站内提醒规则（聚焦改造 P2）。

取代绑定飞书的 NotificationService：所有提醒写入 ``alert`` 表，由前端提醒中心展示，
非静默时段的即时提醒额外经事件总线发布 ``alert.created``（SSE 推给已打开的页面）。

规则：
- **持仓价格**：仅 ``position_size > 0`` 的自选股；|涨跌幅| ≥ ``price_move_percent``（默认 5）；
  只在该市场交易时段内触发。去重键用昨收价区分交易日——节假日行情不更新、昨收不变，
  因此不会把上一个交易日的涨跌重复提醒；缺昨收时退回按本地日期去重。
- **新闻**：标题出现股票简称（中文子串 / 英文整词）或代码，或 A 股规则关联
  （``news_stock_mention`` 置信度 ≥ 0.9，即标题命中）即算命中。持仓股立即提醒；
  仅关注的股票先进内存合并窗口，每 ``watch_digest_minutes`` 合并成一条。
  进程重启会丢失尚未合并的关注股命中（最多一个窗口），持仓提醒不受影响。
- **静默时段**（默认北京时间 22:00～08:00）：提醒照常写库，``overnight=True``，
  ``visible_at`` 推迟到静默结束时刻，不发布 SSE。

P2 的"重大新闻"判断只是标题关键词规则，会有误报；P3 由 AI 判断替换。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.news_stock_mention import NewsStockMention
from app.models.watchlist_item import WatchlistItem
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertView
from app.services.a_share_mentions import MENTION_STOP_NAMES
from app.services.market_hours import is_market_open

logger = logging.getLogger(__name__)

KIND_HOLDING_PRICE_MOVE = "holding_price_move"
KIND_HOLDING_NEWS = "holding_news"
KIND_WATCH_NEWS_DIGEST = "watch_news_digest"
KIND_SENTIMENT_DIVERGENCE = "sentiment_divergence"
SEVERITY_IMMEDIATE = "immediate"
SEVERITY_DIGEST = "digest"
ALERT_CREATED_EVENT = "alert.created"

RULE_MENTION_MIN_CONFIDENCE = 0.9
_NAME_SUFFIX_RE = re.compile(r"[-－](W|SW|U|WD|S)$", re.IGNORECASE)
_CJK_RE = re.compile(r"[一-鿿]")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_hhmm(value: str) -> time:
    hour, minute = value.strip().split(":", 1)
    return time(int(hour), int(minute))


def alert_to_view(alert: Alert) -> AlertView:
    try:
        payload = json.loads(alert.payload_json or "{}")
    except ValueError:
        payload = {}
    return AlertView(
        id=alert.id,
        kind=alert.kind,
        severity=alert.severity,
        symbol=alert.symbol,
        title=alert.title,
        body=alert.body,
        payload=payload if isinstance(payload, dict) else {},
        overnight=alert.overnight,
        created_at=alert.created_at,
        visible_at=alert.visible_at,
        read_at=alert.read_at,
    )


@dataclass(frozen=True)
class _Stock:
    symbol: str
    market: str
    name: str
    is_holding: bool
    position_size: float | None
    average_cost: float | None
    patterns: tuple[re.Pattern[str], ...]


@dataclass
class _DigestHit:
    news_id: int
    symbol: str
    name: str
    title: str
    source_name: str | None


@dataclass
class _DigestWindow:
    start: datetime
    hits: list[_DigestHit] = field(default_factory=list)
    keys: set[tuple[int, str]] = field(default_factory=set)


def _name_patterns(name: str) -> list[re.Pattern[str]]:
    cleaned = _NAME_SUFFIX_RE.sub("", (name or "").strip())
    if not cleaned or cleaned in MENTION_STOP_NAMES:
        return []
    if _CJK_RE.search(cleaned):
        return [re.compile(re.escape(cleaned))] if len(cleaned) >= 2 else []
    if len(cleaned) < 3:
        return []
    return [re.compile(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", re.IGNORECASE)]


def _code_patterns(symbol: str, market: str) -> list[re.Pattern[str]]:
    upper = symbol.upper()
    code, _, exchange = upper.partition(".")
    if market == "cn" or exchange in {"SH", "SZ", "BJ"}:
        return [re.compile(rf"(?<!\d){re.escape(code)}(?!\d)")] if code.isdigit() else []
    if market == "hk" or exchange == "HK":
        digits = code[2:] if code.startswith("HK") else code
        if not digits.isdigit():
            return []
        padded = digits.zfill(5)
        return [
            re.compile(rf"(?<!\d){re.escape(padded)}(?!\d)"),
            re.compile(rf"(?<!\d)0*{re.escape(digits.lstrip('0'))}\.HK\b", re.IGNORECASE),
        ]
    if code.isalpha() and len(code) >= 2:
        return [re.compile(rf"(?<![A-Za-z]){re.escape(code)}(?![A-Za-z])")]
    return []


class AlertService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = SessionLocal,
        event_bus: Any | None = None,
        clock: Callable[[], datetime] = _utc_now,
        price_move_percent: float | None = None,
        quiet_hours: tuple[str, str] | None = None,
        tz_name: str | None = None,
        watch_digest_minutes: int | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._clock = clock
        self._price_move_percent = float(
            settings.alert_price_move_percent if price_move_percent is None else price_move_percent
        )
        start, end = quiet_hours or (settings.alert_quiet_hours_start, settings.alert_quiet_hours_end)
        self._quiet_start = _parse_hhmm(start) if start else None
        self._quiet_end = _parse_hhmm(end) if end else None
        self._tz = ZoneInfo(tz_name or settings.alert_tz)
        self._digest_minutes = int(
            settings.alert_watch_digest_minutes if watch_digest_minutes is None else watch_digest_minutes
        )
        self._digest_lock = threading.Lock()
        self._digest_windows: dict[datetime, _DigestWindow] = {}

    # ------------------------------------------------------------------ 公共入口

    def on_quotes(self, quotes: Iterable[dict[str, Any]]) -> int:
        """行情刷新回调：持仓股 |涨跌幅| 超阈值时写入提醒，返回新建条数。"""
        now = self._clock()
        self.flush_watch_digest()
        with self._session_factory() as session:
            stocks = {stock.symbol: stock for stock in self._load_stocks(session) if stock.is_holding}
            if not stocks:
                return 0
            repo = AlertRepository(session)
            created: list[Alert] = []
            for quote in quotes:
                stock = stocks.get(str(quote.get("symbol") or "").upper())
                change = quote.get("change_percent")
                if stock is None or change is None:
                    continue
                if abs(float(change)) < self._price_move_percent:
                    continue
                if not is_market_open(stock.market, now):
                    continue
                alert = self._create_price_alert(repo, stock, quote, float(change), now)
                if alert is not None:
                    created.append(alert)
            session.commit()
            self._publish(created)
            return len(created)

    def on_news_batch(self, news_items: Iterable[dict[str, Any]]) -> int:
        """新闻评分完成回调：持仓命中立即写提醒，关注股命中进合并窗口；返回立即提醒条数。"""
        now = self._clock()
        items = [item for item in news_items if item.get("id") is not None and item.get("title")]
        self.flush_watch_digest()
        if not items:
            return 0
        with self._session_factory() as session:
            stocks = self._load_stocks(session)
            if not stocks:
                return 0
            by_symbol = {stock.symbol: stock for stock in stocks}
            mention_hits = self._load_rule_mentions(session, [int(item["id"]) for item in items], by_symbol)
            repo = AlertRepository(session)
            created: list[Alert] = []
            for item in items:
                news_id = int(item["id"])
                title = str(item["title"])
                matched = {
                    stock.symbol for stock in stocks if any(pattern.search(title) for pattern in stock.patterns)
                }
                matched |= mention_hits.get(news_id, set())
                for symbol in sorted(matched):
                    stock = by_symbol[symbol]
                    if stock.is_holding:
                        alert = self._create_news_alert(repo, stock, item, now)
                        if alert is not None:
                            created.append(alert)
                    else:
                        self._buffer_digest_hit(stock, item, now)
            session.commit()
            self._publish(created)
            return len(created)

    def flush_watch_digest(self) -> int:
        """把已结束的合并窗口各写成一条 ``watch_news_digest`` 提醒，返回写入条数。"""
        now = self._clock()
        with self._digest_lock:
            due = [
                window
                for start, window in self._digest_windows.items()
                if start + timedelta(minutes=self._digest_minutes) <= now
            ]
            for window in due:
                self._digest_windows.pop(window.start, None)
        if not due:
            return 0
        created: list[Alert] = []
        with self._session_factory() as session:
            repo = AlertRepository(session)
            for window in sorted(due, key=lambda w: w.start):
                if not window.hits:
                    continue
                alert = self._create_digest_alert(repo, window, now)
                if alert is not None:
                    created.append(alert)
            session.commit()
            self._publish(created)
        return len(created)

    def on_sentiment_divergence(self, payload: dict[str, Any]) -> int:
        """情绪-价格背离提醒（功能开关 ``sentiment_divergence_alert_enabled`` 默认关闭）。"""
        symbol = payload.get("symbol")
        status_value = payload.get("status")
        if not symbol or not status_value:
            return 0
        now = self._clock()
        overnight, visible_at = self._visibility(now)
        with self._session_factory() as session:
            alert = AlertRepository(session).create_if_absent(
                kind=KIND_SENTIMENT_DIVERGENCE,
                severity=SEVERITY_IMMEDIATE,
                symbol=str(symbol),
                title=f"{payload.get('display_name') or symbol} 情绪与价格背离",
                body=str(payload.get("message") or status_value),
                payload=payload,
                dedupe_key=f"divergence:{symbol}:{status_value}:{self._local_date(now).isoformat()}",
                overnight=overnight,
                visible_at=visible_at,
                created_at=now,
            )
            session.commit()
            self._publish([alert] if alert is not None else [])
            return 1 if alert is not None else 0

    # ------------------------------------------------------------------ 规则细节

    def _create_price_alert(
        self, repo: AlertRepository, stock: _Stock, quote: dict[str, Any], change: float, now: datetime
    ) -> Alert | None:
        price = quote.get("price")
        previous_close = quote.get("previous_close")
        day_marker = (
            f"{float(previous_close):.4f}" if previous_close is not None else self._local_date(now).isoformat()
        )
        direction = "涨" if change > 0 else "跌"
        body_parts: list[str] = []
        if price is not None:
            prev_text = f"（昨收 {float(previous_close):.2f}）" if previous_close is not None else ""
            body_parts.append(f"现价 {float(price):.2f}{prev_text}")
        if stock.position_size:
            holding = f"持仓 {stock.position_size:g} 股"
            if stock.average_cost is not None and price is not None:
                pnl = (float(price) - stock.average_cost) * stock.position_size
                holding += f"，成本 {stock.average_cost:.2f}，浮动盈亏 {pnl:+,.0f}"
            body_parts.append(holding)
        overnight, visible_at = self._visibility(now)
        return repo.create_if_absent(
            kind=KIND_HOLDING_PRICE_MOVE,
            severity=SEVERITY_IMMEDIATE,
            symbol=stock.symbol,
            title=f"{stock.name} {direction} {abs(change):.2f}%",
            body=" · ".join(body_parts),
            payload={
                "change_percent": change,
                "price": price,
                "previous_close": previous_close,
                "position_size": stock.position_size,
                "average_cost": stock.average_cost,
                "threshold": self._price_move_percent,
            },
            dedupe_key=f"price:{stock.symbol}:{day_marker}",
            overnight=overnight,
            visible_at=visible_at,
            created_at=now,
        )

    def _create_news_alert(
        self, repo: AlertRepository, stock: _Stock, item: dict[str, Any], now: datetime
    ) -> Alert | None:
        news_id = int(item["id"])
        overnight, visible_at = self._visibility(now)
        return repo.create_if_absent(
            kind=KIND_HOLDING_NEWS,
            severity=SEVERITY_IMMEDIATE,
            symbol=stock.symbol,
            title=f"{stock.name}：{item['title']}",
            body=str(item.get("source_name") or ""),
            payload={
                "news_id": news_id,
                "news_title": item["title"],
                "source_name": item.get("source_name"),
                "market": item.get("market"),
            },
            dedupe_key=f"news:{news_id}:{stock.symbol}",
            overnight=overnight,
            visible_at=visible_at,
            created_at=now,
        )

    def _buffer_digest_hit(self, stock: _Stock, item: dict[str, Any], now: datetime) -> None:
        window_start = self._window_start(now)
        key = (int(item["id"]), stock.symbol)
        with self._digest_lock:
            window = self._digest_windows.setdefault(window_start, _DigestWindow(start=window_start))
            if key in window.keys:
                return
            window.keys.add(key)
            window.hits.append(
                _DigestHit(
                    news_id=int(item["id"]),
                    symbol=stock.symbol,
                    name=stock.name,
                    title=str(item["title"]),
                    source_name=item.get("source_name"),
                )
            )

    def _create_digest_alert(self, repo: AlertRepository, window: _DigestWindow, now: datetime) -> Alert | None:
        names: list[str] = []
        for hit in window.hits:
            if hit.name not in names:
                names.append(hit.name)
        overnight, visible_at = self._visibility(now)
        return repo.create_if_absent(
            kind=KIND_WATCH_NEWS_DIGEST,
            severity=SEVERITY_DIGEST,
            symbol=None,
            title=f"关注股新闻 {len(window.hits)} 条：{'、'.join(names[:3])}{' 等' if len(names) > 3 else ''}",
            body="\n".join(f"{hit.name}：{hit.title}" for hit in window.hits[:20]),
            payload={
                "window_start": window.start.isoformat(),
                "items": [
                    {"news_id": hit.news_id, "symbol": hit.symbol, "name": hit.name, "title": hit.title}
                    for hit in window.hits
                ],
            },
            dedupe_key=f"watch_digest:{window.start.isoformat()}",
            overnight=overnight,
            visible_at=visible_at,
            created_at=now,
        )

    # ------------------------------------------------------------------ 工具

    def _load_stocks(self, session: Any) -> list[_Stock]:
        stocks: list[_Stock] = []
        for item in session.scalars(select(WatchlistItem).where(WatchlistItem.is_active.is_(True))):
            name = (item.display_name or item.symbol).strip()
            patterns = tuple(_name_patterns(name) + _code_patterns(item.symbol, item.market))
            stocks.append(
                _Stock(
                    symbol=item.symbol.upper(),
                    market=item.market,
                    name=name,
                    is_holding=bool(item.position_size and item.position_size > 0),
                    position_size=item.position_size,
                    average_cost=item.average_cost,
                    patterns=patterns,
                )
            )
        return stocks

    @staticmethod
    def _load_rule_mentions(
        session: Any, news_ids: list[int], by_symbol: dict[str, _Stock]
    ) -> dict[int, set[str]]:
        rows = session.execute(
            select(NewsStockMention.news_id, NewsStockMention.symbol).where(
                NewsStockMention.news_id.in_(news_ids),
                NewsStockMention.symbol.in_(list(by_symbol)),
                NewsStockMention.confidence >= RULE_MENTION_MIN_CONFIDENCE,
            )
        )
        hits: dict[int, set[str]] = {}
        for news_id, symbol in rows:
            hits.setdefault(int(news_id), set()).add(str(symbol).upper())
        return hits

    def _window_start(self, now: datetime) -> datetime:
        minutes = max(1, self._digest_minutes)
        epoch_minutes = int(now.timestamp() // 60)
        return datetime.fromtimestamp((epoch_minutes - epoch_minutes % minutes) * 60, tz=UTC)

    def _local_date(self, now: datetime) -> date:
        return now.astimezone(self._tz).date()

    def _visibility(self, now: datetime) -> tuple[bool, datetime]:
        """返回 (是否静默时段, 可见时刻)。静默期可见时刻为静默结束（本地时间）。"""
        if self._quiet_start is None or self._quiet_end is None or self._quiet_start == self._quiet_end:
            return False, now
        local = now.astimezone(self._tz)
        current = local.time()
        start, end = self._quiet_start, self._quiet_end
        if start < end:
            in_quiet = start <= current < end
            visible_date = local.date()
        else:  # 跨午夜窗口
            in_quiet = current >= start or current < end
            visible_date = local.date() + timedelta(days=1) if current >= start else local.date()
        if not in_quiet:
            return False, now
        visible_local = datetime.combine(visible_date, end, tzinfo=self._tz)
        return True, visible_local.astimezone(UTC)

    def _publish(self, alerts: list[Alert]) -> None:
        if not alerts:
            return
        bus = self._event_bus
        if bus is None:
            from app.services.event_bus import get_event_bus

            bus = get_event_bus()
        for alert in alerts:
            if alert.overnight:
                continue
            try:
                bus.publish(ALERT_CREATED_EVENT, alert_to_view(alert).model_dump(mode="json"))
            except Exception:
                logger.warning("failed to publish alert.created for alert_id=%s", alert.id, exc_info=True)


_service: AlertService | None = None
_service_lock = threading.Lock()


def get_alert_service() -> AlertService:
    global _service
    with _service_lock:
        if _service is None:
            _service = AlertService()
        return _service


def reset_alert_service() -> None:
    """测试用：清空单例（配置变更后重建）。"""
    global _service
    with _service_lock:
        _service = None
