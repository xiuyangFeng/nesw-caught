from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_repository import MarketRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.quote_provider import NormalizedSymbol, QuoteRecord, YahooFinanceQuoteProvider, normalize_symbol


class QuoteService:
    def __init__(self) -> None:
        settings = get_settings()
        self.cache_ttl = timedelta(seconds=settings.market_quote_cache_ttl_seconds)
        self.provider = YahooFinanceQuoteProvider()

    def refresh_watchlist_quotes(self, session: Session) -> list[dict]:
        repository = WatchlistRepository(session)
        items = repository.list_all()
        return [self._get_quote_payload(session, item.symbol, item.market, item.display_name) for item in items]

    def get_cached_watchlist_quotes(self, session: Session) -> list[dict]:
        repository = WatchlistRepository(session)
        items = repository.list_all()
        market_repo = MarketRepository(session)
        cached = market_repo.list_latest_by_symbols([item.symbol for item in items])
        payloads: list[dict] = []
        for item in items:
            snapshot = cached.get(item.symbol)
            if snapshot is None:
                payloads.append(
                    self._build_unavailable_payload(
                        item.symbol,
                        item.market,
                        item.display_name,
                        "unavailable",
                        "quote not produced yet",
                    )
                )
                continue
            payloads.append(self._snapshot_to_read_payload(snapshot, item.display_name))
        return payloads

    def get_cached_symbol_quote(self, symbol: str, session: Session) -> dict:
        repository = WatchlistRepository(session)
        item = repository.get_by_symbol(symbol.upper())
        market = item.market if item else None
        display_name = item.display_name if item else None
        try:
            normalized = normalize_symbol(symbol.upper(), market)
            lookup_symbol = normalized.symbol
            lookup_market = normalized.market
        except ValueError as exc:
            return self._build_unavailable_payload(symbol.upper(), market or "unknown", display_name, "symbol_not_supported", str(exc))

        market_repo = MarketRepository(session)
        snapshot = market_repo.list_latest_by_symbols([lookup_symbol]).get(lookup_symbol)
        if snapshot is None:
            return self._build_unavailable_payload(
                lookup_symbol,
                lookup_market,
                display_name,
                "unavailable",
                "quote not produced yet",
                normalized.provider_symbol,
            )
        return self._snapshot_to_read_payload(snapshot, display_name)

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

        cached = market_repo.list_latest_by_symbols([symbol]).get(symbol)
        if cached and self._is_fresh(cached):
            return self._snapshot_to_payload(cached, display_name)

        try:
            live_quote = self.provider.fetch_quote(normalized)
            snapshot = self._save_live_quote(session, market_repo, live_quote)
            return self._snapshot_to_payload(snapshot, display_name)
        except Exception as exc:  # pragma: no cover - network/provider behavior
            if cached:
                payload = self._snapshot_to_payload(cached, display_name)
                payload["status"] = "delayed"
                payload["message"] = str(exc)
                return payload
            return self._build_unavailable_payload(symbol, normalized.market, display_name, "fetch_failed", str(exc), normalized.provider_symbol)

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
        return market_repo.save_snapshot(snapshot)

    def _snapshot_to_payload(self, snapshot: PriceSnapshot, display_name: str | None) -> dict:
        is_abnormal = abs(snapshot.change_percent or 0.0) >= 3
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
        }

    def _snapshot_to_read_payload(self, snapshot: PriceSnapshot, display_name: str | None) -> dict:
        payload = self._snapshot_to_payload(snapshot, display_name)
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
            "fetched_at": datetime.now(timezone.utc),
            "is_abnormal": False,
            "abnormal_reason": None,
        }

    def _is_fresh(self, snapshot: PriceSnapshot) -> bool:
        fetched_at = snapshot.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched_at <= self.cache_ttl
