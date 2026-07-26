from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings

# SessionLocal 在模块顶层导入是安全的：app.db.session 只依赖 app.core.config，
# 不会反向导入任何 service，因此不存在循环 import。此前这里漏了这行 import，
# 导致 get_cached_symbol_quote 的“零延迟保底”分支一执行就抛 NameError。
from app.db.session import SessionLocal
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_repository import MarketRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.quote_provider import (
    NormalizedSymbol,
    QuoteRecord,
    TencentQuoteProvider,
    YahooFinanceQuoteProvider,
    equivalent_symbol_candidates,
    normalize_symbol,
)

# 此前模块里没有定义 logger，异常分支里的 logger.warning 会再抛一次 NameError，
# 把一次可降级的抓取失败放大成 500。
logger = logging.getLogger(__name__)

# 腾讯回落接口是一次请求带多个 code 的批量接口；code 太多会让单条 URL 过长、
# 单次超时（5s）覆盖的标的过多。按块切分后并发抓取，块内仍复用批量语义。
_FALLBACK_CHUNK_SIZE = 20


class QuoteService:
    def __init__(self) -> None:
        settings = get_settings()
        self.cache_ttl = timedelta(seconds=settings.market_quote_cache_ttl_seconds)
        self.provider = YahooFinanceQuoteProvider()
        self.fallback_provider = TencentQuoteProvider()
        self._max_workers = max(1, int(getattr(settings, "market_chart_max_workers", 8)))
        self._hot_symbols_cache: set[str] | None = None
        self._hot_symbols_cached_at: datetime | None = None

    def _get_hot_symbols(self, session: Session) -> set[str]:
        now = datetime.now(UTC)
        if (
            self._hot_symbols_cache is not None
            and self._hot_symbols_cached_at is not None
            and now - self._hot_symbols_cached_at < timedelta(seconds=60)
        ):
            return set(self._hot_symbols_cache)

    def refresh_watchlist_quotes(self, session: Session) -> list[dict]:
        repository = WatchlistRepository(session)
        items = repository.list_all()
        if not items:
            return []

        market_repo = MarketRepository(session)

        # 1. Batch lookup normalization and cache snapshots
        symbols_to_lookup = []
        normalized_map = {}
        for item in items:
            try:
                ns = normalize_symbol(item.symbol, item.market)
                normalized_map[item.symbol] = ns
                symbols_to_lookup.append(ns.symbol)
            except ValueError as exc:
                normalized_map[item.symbol] = exc

        symbols_to_lookup = list(set(symbols_to_lookup))
        cached_snapshots = market_repo.list_latest_by_symbols(symbols_to_lookup)

        # 2. Categorize items into cache hits or need refresh
        to_fetch_yahoo = []
        results = {}

        for item in items:
            ns_or_exc = normalized_map.get(item.symbol)
            if isinstance(ns_or_exc, ValueError):
                results[item.symbol] = self._build_unavailable_payload(
                    item.symbol, item.market or "unknown", item.display_name, "symbol_not_supported", str(ns_or_exc)
                )
                continue

            ns = ns_or_exc
            cached = cached_snapshots.get(ns.symbol)
            if cached and self._is_fresh(cached):
                results[item.symbol] = self._snapshot_to_payload(cached, item.display_name)
            else:
                to_fetch_yahoo.append((item, ns, cached))

        # 3. 阶段一：**只联网，不写库**。
        #    此前的写法是「Yahoo 批量抓取 -> 逐条 add/flush/refresh（写事务已开启）
        #    -> 再发起腾讯回落的 HTTP 抓取 -> 最后才 commit」，SQLite 的写锁会
        #    横跨整段网络调用，其它写者（ingestion / queue worker / notification）
        #    只能在 busy_timeout 内排队。现在把全部网络抓取前置，拿齐所有
        #    QuoteRecord 之后才进入写事务。
        if to_fetch_yahoo:
            yahoo_ns_list = [ns for _, ns, _ in to_fetch_yahoo]
            yahoo_records = self.provider.fetch_quotes_batch(yahoo_ns_list)
            yahoo_records_map = {r.symbol: r for r in yahoo_records}

            # resolved 元素：(item, ns, cached, ok_record | None, failure_message | None)
            resolved: list[tuple[object, object, PriceSnapshot | None, QuoteRecord | None, str | None]] = []
            to_fetch_tencent = []

            for item, ns, cached in to_fetch_yahoo:
                record = yahoo_records_map.get(ns.symbol)

                # Check if it failed and is eligible for tencent fallback (cn/hk)
                if (not record or record.status != "ok") and ns.market in ("cn", "hk"):
                    to_fetch_tencent.append((item, ns, cached, record))
                elif record and record.status == "ok":
                    resolved.append((item, ns, cached, record, None))
                else:
                    exc_msg = record.message if record else "fetch returned empty"
                    resolved.append((item, ns, cached, None, exc_msg))

            # 4. 腾讯回落同样在写事务之前完成；多标的按块并发。
            if to_fetch_tencent:
                tencent_ns_list = [ns for _, ns, _, _ in to_fetch_tencent]
                tencent_records_map = self._fetch_fallback_quotes(tencent_ns_list)

                for item, ns, cached, yahoo_record in to_fetch_tencent:
                    record = tencent_records_map.get(ns.symbol)
                    if record and record.status == "ok":
                        resolved.append((item, ns, cached, record, None))
                    else:
                        yahoo_msg = yahoo_record.message if yahoo_record else "Yahoo fetch failed"
                        tencent_msg = record.message if record else "Tencent fetch failed"
                        merged_msg = f"Yahoo: {yahoo_msg}; Fallback Tencent: {tencent_msg}"
                        resolved.append((item, ns, cached, None, merged_msg))

            # 5. 阶段二：**只写库，不联网**。写事务窗口收敛成一次纯本地 flush + 单次 commit。
            for item, ns, cached, record, failure_msg in resolved:
                if record is not None:
                    snapshot = self._save_live_quote(session, market_repo, record, auto_commit=False)
                    results[item.symbol] = self._snapshot_to_payload(snapshot, item.display_name)
                elif cached:
                    payload = self._snapshot_to_payload(cached, item.display_name)
                    payload["status"] = "delayed"
                    payload["message"] = failure_msg
                    results[item.symbol] = payload
                else:
                    results[item.symbol] = self._build_unavailable_payload(
                        item.symbol, ns.market, item.display_name, "fetch_failed", failure_msg, ns.provider_symbol
                    )

            session.commit()

        return [results[item.symbol] for item in items]

    def _fetch_fallback_quotes(self, normalized_list: list[NormalizedSymbol]) -> dict[str, QuoteRecord]:
        """并发抓取腾讯回落行情，返回 {symbol: QuoteRecord}。

        TencentQuoteProvider.fetch_quotes_batch 本身会把一组 code 合并成一次
        HTTP 请求，因此只有在标的数超过一个分块时才真正需要并发；单块时保持
        原来的“一次请求”语义（既有测试断言 fallback provider 只被调用一次）。
        任一分块异常都只影响该分块，不会让整轮刷新失败。
        """
        if not normalized_list:
            return {}

        chunks = [
            normalized_list[index : index + _FALLBACK_CHUNK_SIZE]
            for index in range(0, len(normalized_list), _FALLBACK_CHUNK_SIZE)
        ]
        if len(chunks) == 1:
            return {record.symbol: record for record in self._fetch_fallback_chunk(chunks[0])}

        records_map: dict[str, QuoteRecord] = {}
        with ThreadPoolExecutor(max_workers=min(len(chunks), self._max_workers)) as pool:
            for records in pool.map(self._fetch_fallback_chunk, chunks):
                for record in records:
                    records_map[record.symbol] = record
        return records_map

    def _fetch_fallback_chunk(self, chunk: list[NormalizedSymbol]) -> list[QuoteRecord]:
        try:
            return self.fallback_provider.fetch_quotes_batch(chunk)
        except Exception as exc:  # pragma: no cover - 网络/provider 异常
            logger.warning("tencent fallback batch failed (%d symbols): %s", len(chunk), exc)
            return []


    def get_cached_watchlist_quotes(self, session: Session) -> list[dict]:
        repository = WatchlistRepository(session)
        items = repository.list_all()
        market_repo = MarketRepository(session)
        hot_symbols = self._get_hot_symbols(session)
        lookup_by_item_symbol: dict[str, str] = {}
        for item in items:
            try:
                lookup_by_item_symbol[item.symbol] = normalize_symbol(item.symbol, item.market).symbol
            except ValueError:
                lookup_by_item_symbol[item.symbol] = item.symbol
        cached = market_repo.list_latest_by_symbols(list(dict.fromkeys(lookup_by_item_symbol.values())))
        payloads: list[dict] = []
        for item in items:
            snapshot = cached.get(lookup_by_item_symbol[item.symbol])
            is_hot = item.symbol in hot_symbols or lookup_by_item_symbol[item.symbol] in hot_symbols
            if snapshot is None:
                payloads.append(
                    self._build_unavailable_payload(
                        lookup_by_item_symbol[item.symbol],
                        item.market,
                        item.display_name,
                        "unavailable",
                        "quote not produced yet",
                        has_hot_alert=is_hot,
                    )
                )
                continue
            payloads.append(self._snapshot_to_read_payload(snapshot, item.display_name, hot_symbols))
        return payloads

    def get_cached_symbol_quote(self, symbol: str, session: Session) -> dict:
        repository = WatchlistRepository(session)
        item = None
        for candidate in equivalent_symbol_candidates(symbol):
            item = repository.get_by_symbol(candidate)
            if item is not None:
                break
        market = item.market if item else None
        display_name = item.display_name if item else None
        try:
            normalized = normalize_symbol(symbol.upper(), market)
            if item is None:
                for candidate in equivalent_symbol_candidates(symbol, normalized.market):
                    item = repository.get_by_symbol(candidate)
                    if item is not None:
                        break
                market = item.market if item else normalized.market
                display_name = item.display_name if item else display_name
            lookup_symbol = normalized.symbol
            lookup_market = normalized.market
        except ValueError as exc:
            return self._build_unavailable_payload(symbol.upper(), market or "unknown", display_name, "symbol_not_supported", str(exc))

        market_repo = MarketRepository(session)
        snapshot = market_repo.list_latest_by_symbols([lookup_symbol]).get(lookup_symbol)
        hot_symbols = self._get_hot_symbols(session)
        is_hot = symbol.upper() in hot_symbols or lookup_symbol in hot_symbols

        if snapshot is not None:
            return self._snapshot_to_read_payload(snapshot, display_name, hot_symbols)

        # 🌟 零延迟保底机制：刚添加的标的若尚未被 worker 轮询产生快照，透明即时抓取并存库。
        # 注意执行顺序：网络抓取全部完成后才开写事务（下面的 SessionLocal 块），
        # 写事务里只有一次 add/flush/commit，不夹带任何网络调用。
        # 这里刻意用独立的短写会话，而不是请求级的 session：请求级 session 在整个
        # handler 期间存活，用它写会把写事务的存活期拉长到 handler 结束。
        try:
            live_quote = self.provider.fetch_quote(normalized)
            if live_quote.status != "ok" and normalized.market in ("cn", "hk"):
                fallback_quote = self.fallback_provider.fetch_quote(normalized)
                if fallback_quote.status == "ok":
                    live_quote = fallback_quote
            if live_quote.status == "ok":
                with SessionLocal() as local_session:
                    local_market_repo = MarketRepository(local_session)
                    saved_snapshot = self._save_live_quote(local_session, local_market_repo, live_quote)
                    local_session.commit()
                    return self._snapshot_to_read_payload(saved_snapshot, display_name, hot_symbols)
        except Exception as exc:
            logger.warning("on-demand instant quote fetch failed for %s: %s", lookup_symbol, exc)

        return self._build_unavailable_payload(
            lookup_symbol,
            lookup_market,
            display_name,
            "unavailable",
            "quote not produced yet",
            normalized.provider_symbol,
            has_hot_alert=is_hot,
        )

    def _get_quote_payload(
        self,
        session: Session,
        symbol: str,
        market: str | None,
        display_name: str | None,
    ) -> dict:
        market_repo = MarketRepository(session)
        try:
            normalized = normalize_symbol(symbol, market)
        except ValueError as exc:
            return self._build_unavailable_payload(symbol, market or "unknown", display_name, "symbol_not_supported", str(exc))

        hot_symbols = self._get_hot_symbols(session)
        cached = market_repo.list_latest_by_symbols([normalized.symbol]).get(normalized.symbol)
        is_hot = symbol.upper() in hot_symbols or normalized.symbol in hot_symbols
        if cached and self._is_fresh(cached):
            return self._snapshot_to_payload(cached, display_name, hot_symbols)

        try:
            live_quote = self.provider.fetch_quote(normalized)
            snapshot = self._save_live_quote(session, market_repo, live_quote)
            return self._snapshot_to_payload(snapshot, display_name, hot_symbols)
        except Exception as exc:  # pragma: no cover - network/provider behavior
            if cached:
                payload = self._snapshot_to_payload(cached, display_name, hot_symbols)
                payload["status"] = "delayed"
                payload["message"] = str(exc)
                return payload
            return self._build_unavailable_payload(symbol, normalized.market, display_name, "fetch_failed", str(exc), normalized.provider_symbol, has_hot_alert=is_hot)

    def _save_live_quote(
        self,
        session: Session,
        market_repo: MarketRepository,
        quote: QuoteRecord,
        *,
        auto_commit: bool = True,
    ) -> PriceSnapshot:
        snapshot = PriceSnapshot(
            symbol=quote.symbol,
            market=quote.market,
            price=quote.price or 0.0,
            change_amount=quote.change_amount,
            change_percent=quote.change_percent,
            open_price=quote.open_price,
            previous_close=quote.previous_close,
            day_high=quote.day_high,
            day_low=quote.day_low,
            volume=quote.volume,
            provider_name=quote.source,
            provider_symbol=quote.provider_symbol,
            quote_status=quote.status,
            status_message=quote.message,
            fetched_at=quote.fetched_at,
        )
        saved = market_repo.save_snapshot(snapshot)
        if auto_commit:
            session.commit()
        return saved

    def _snapshot_to_payload(self, snapshot: PriceSnapshot, display_name: str | None, hot_symbols: set[str] | None = None) -> dict:
        is_abnormal = abs(snapshot.change_percent or 0.0) >= 3
        has_hot_alert = False
        if hot_symbols and snapshot.symbol in hot_symbols:
            has_hot_alert = True
        return {
            "symbol": snapshot.symbol,
            "market": snapshot.market,
            "display_name": display_name,
            "provider_symbol": snapshot.provider_symbol,
            "price": snapshot.price,
            "change_amount": snapshot.change_amount,
            "change_percent": snapshot.change_percent,
            "open_price": snapshot.open_price,
            "previous_close": snapshot.previous_close,
            "day_high": snapshot.day_high,
            "day_low": snapshot.day_low,
            "volume": snapshot.volume,
            "status": snapshot.quote_status or "ok",
            "source": snapshot.provider_name,
            "message": snapshot.status_message,
            "fetched_at": snapshot.fetched_at,
            "is_abnormal": is_abnormal,
            "abnormal_reason": "price_move" if is_abnormal else None,
            "has_hot_alert": has_hot_alert,
        }

    def _snapshot_to_read_payload(self, snapshot: PriceSnapshot, display_name: str | None, hot_symbols: set[str] | None = None) -> dict:
        payload = self._snapshot_to_payload(snapshot, display_name, hot_symbols)
        if payload["status"] == "ok" and not self._is_fresh(snapshot):
            payload["status"] = "delayed"
            payload["message"] = payload["message"] or "stale quote snapshot"
        return payload

    def _build_unavailable_payload(
        self,
        symbol: str,
        market: str,
        display_name: str | None,
        status: str,
        message: str,
        provider_symbol: str | None = None,
        has_hot_alert: bool = False,
    ) -> dict:
        return {
            "symbol": symbol,
            "market": market,
            "display_name": display_name,
            "provider_symbol": provider_symbol,
            "price": None,
            "change_amount": None,
            "change_percent": None,
            "open_price": None,
            "previous_close": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "status": status,
            "source": self.provider.source_name,
            "message": message,
            "fetched_at": datetime.now(UTC),
            "is_abnormal": False,
            "abnormal_reason": None,
            "has_hot_alert": has_hot_alert,
        }

    def _is_fresh(self, snapshot: PriceSnapshot) -> bool:
        fetched_at = snapshot.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age = datetime.now(UTC) - fetched_at
        return age <= self.cache_ttl or age.total_seconds() < 0
    _hot_symbols_cache: set[str] = set()
    _hot_symbols_cached_at: datetime | None = None
    _hot_symbols_lock = threading.Lock()

    def _get_hot_symbols(self, session: Session) -> set[str]:
        now = datetime.now(UTC)
        with QuoteService._hot_symbols_lock:
            if (
                QuoteService._hot_symbols_cached_at is not None
                and now - QuoteService._hot_symbols_cached_at < timedelta(seconds=60)
            ):
                return set(QuoteService._hot_symbols_cache)

        from sqlalchemy import or_, select

        from app.models.news_item import NewsItem
        from app.models.news_stock_mention import NewsStockMention
        from app.models.topic_cluster import TopicCluster
        from app.models.topic_news_link import TopicNewsLink
        limit_time = now - timedelta(hours=12)
        stmt = (
            select(NewsStockMention.symbol)
            .join(NewsItem, NewsStockMention.news_id == NewsItem.id)
            .outerjoin(TopicNewsLink, NewsItem.id == TopicNewsLink.news_id)
            .outerjoin(TopicCluster, TopicNewsLink.topic_cluster_id == TopicCluster.id)
            .where(NewsItem.published_at >= limit_time)
            .where(
                or_(
                    NewsItem.sentiment_score >= 0.8,
                    NewsItem.sentiment_score <= -0.8,
                    TopicCluster.importance_score >= 8.0
                )
            )
        )
        try:
            results = set(session.scalars(stmt).all())
            with QuoteService._hot_symbols_lock:
                QuoteService._hot_symbols_cache = results
                QuoteService._hot_symbols_cached_at = now
            return results
        except Exception:
            return set()


def clear_hot_symbols_cache() -> None:
    """清空热股 alert 缓存（主要用于测试与实时数据更新后）。"""
    with QuoteService._hot_symbols_lock:
        QuoteService._hot_symbols_cache.clear()
        QuoteService._hot_symbols_cached_at = None
