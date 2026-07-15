from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_repository import MarketRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.quote_provider import (
    QuoteRecord,
    TencentQuoteProvider,
    YahooFinanceQuoteProvider,
    equivalent_symbol_candidates,
    normalize_symbol,
)


class QuoteService:
    def __init__(self) -> None:
        settings = get_settings()
        self.cache_ttl = timedelta(seconds=settings.market_quote_cache_ttl_seconds)
        self.provider = YahooFinanceQuoteProvider()
        self.fallback_provider = TencentQuoteProvider()

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

        # 3. Batch fetch with Yahoo Finance
        if to_fetch_yahoo:
            yahoo_ns_list = [ns for _, ns, _ in to_fetch_yahoo]
            yahoo_records = self.provider.fetch_quotes_batch(yahoo_ns_list)
            yahoo_records_map = {r.symbol: r for r in yahoo_records}

            to_fetch_tencent = []

            for item, ns, cached in to_fetch_yahoo:
                record = yahoo_records_map.get(ns.symbol)

                # Check if it failed and is eligible for tencent fallback (cn/hk)
                if (not record or record.status != "ok") and ns.market in ("cn", "hk"):
                    to_fetch_tencent.append((item, ns, cached, record))
                else:
                    if record and record.status == "ok":
                        snapshot = self._save_live_quote(session, market_repo, record)
                        results[item.symbol] = self._snapshot_to_payload(snapshot, item.display_name)
                    else:
                        exc_msg = record.message if record else "fetch returned empty"
                        if cached:
                            payload = self._snapshot_to_payload(cached, item.display_name)
                            payload["status"] = "delayed"
                            payload["message"] = exc_msg
                            results[item.symbol] = payload
                        else:
                            results[item.symbol] = self._build_unavailable_payload(
                                item.symbol, ns.market, item.display_name, "fetch_failed", exc_msg, ns.provider_symbol
                            )

            # 4. Batch fetch with Tencent Finance for fallbacks
            if to_fetch_tencent:
                tencent_ns_list = [ns for _, ns, _, _ in to_fetch_tencent]
                tencent_records = self.fallback_provider.fetch_quotes_batch(tencent_ns_list)
                tencent_records_map = {r.symbol: r for r in tencent_records}

                for item, ns, cached, yahoo_record in to_fetch_tencent:
                    record = tencent_records_map.get(ns.symbol)
                    if record and record.status == "ok":
                        snapshot = self._save_live_quote(session, market_repo, record)
                        results[item.symbol] = self._snapshot_to_payload(snapshot, item.display_name)
                    else:
                        yahoo_msg = yahoo_record.message if yahoo_record else "Yahoo fetch failed"
                        tencent_msg = record.message if record else "Tencent fetch failed"
                        merged_msg = f"Yahoo: {yahoo_msg}; Fallback Tencent: {tencent_msg}"

                        if cached:
                            payload = self._snapshot_to_payload(cached, item.display_name)
                            payload["status"] = "delayed"
                            payload["message"] = merged_msg
                            results[item.symbol] = payload
                        else:
                            results[item.symbol] = self._build_unavailable_payload(
                                item.symbol, ns.market, item.display_name, "fetch_failed", merged_msg, ns.provider_symbol
                            )

        return [results[item.symbol] for item in items]


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
        if snapshot is None:
            return self._build_unavailable_payload(
                lookup_symbol,
                lookup_market,
                display_name,
                "unavailable",
                "quote not produced yet",
                normalized.provider_symbol,
                has_hot_alert=is_hot,
            )
        return self._snapshot_to_read_payload(snapshot, display_name, hot_symbols)

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

    def _save_live_quote(self, session: Session, market_repo: MarketRepository, quote: QuoteRecord) -> PriceSnapshot:
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
        # 立即提交快照：本方法在 worker 与请求两种上下文中被调用，且调用方
        # 随后可能继续执行慢速网络抓取（Yahoo/Tencent 批量回退），必须避免
        # 把 SQLite 写事务悬挂在网络 IO 期间（repository 层只 flush 不提交）。
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
        return datetime.now(UTC) - fetched_at <= self.cache_ttl

    def _get_hot_symbols(self, session: Session) -> set[str]:
        from sqlalchemy import or_, select

        from app.models.news_item import NewsItem
        from app.models.news_stock_mention import NewsStockMention
        from app.models.topic_cluster import TopicCluster
        from app.models.topic_news_link import TopicNewsLink
        limit_time = datetime.now(UTC) - timedelta(hours=12)
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
            return set(session.scalars(stmt).all())
        except Exception:
            return set()
