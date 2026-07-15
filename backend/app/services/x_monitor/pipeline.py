from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.x_account_repository import XAccountRepository
from app.repositories.x_post_repository import XPostRepository
from app.repositories.x_source_health_repository import XSourceHealthRepository
from app.schemas.x_monitor import XPostSummaryView
from app.services.twitterapi_io_client import TwitterApiIoClient, TwitterApiIoError
from app.services.x_radar_signal_builder import XRadarSignalBuilder

from .constants import PROVIDER_NAME, VALID_SENTIMENTS
from .health import _record_fetch_failure, _record_fetch_success
from .normalize import (
    _dedupe_hash,
    _ensure_enabled,
    _extract_post_id,
    _normalize_datetime,
    _tweet_summary_view,
    _utc_now,
)
from .summaries import XRefreshSummary


class XFetchPipeline:
    """Provider fetch pipeline: refresh with dedupe/persist, health accounting, provider queries."""

    def __init__(
        self,
        session: Session,
        settings,
        *,
        accounts: XAccountRepository,
        posts: XPostRepository,
        health_repo: XSourceHealthRepository,
        provider: TwitterApiIoClient,
        signal_builder: XRadarSignalBuilder,
    ) -> None:
        self.session = session
        self.settings = settings
        self.accounts = accounts
        self.posts = posts
        self.health_repo = health_repo
        self.provider = provider
        self.signal_builder = signal_builder

    def _cooldown_next_refresh_at(self, last_success_at: datetime | None) -> datetime | None:
        if last_success_at is None:
            return None
        cooldown_hours = max(0, int(getattr(self.settings, "x_monitor_refresh_cooldown_hours", 3)))
        return _normalize_datetime(last_success_at) + timedelta(hours=cooldown_hours)

    def refresh(self) -> XRefreshSummary:
        _ensure_enabled(self.settings)
        active_accounts = self.accounts.list_refresh_targets()
        started_at = _utc_now()
        health = self.health_repo.get_or_create(PROVIDER_NAME)

        if not active_accounts:
            finished_at = _utc_now()
            self.session.commit()
            return XRefreshSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_count=0,
                inserted_count=0,
                error=None,
                latency_ms=(finished_at - started_at).total_seconds() * 1000,
                next_refresh_at=None,
            )

        next_refresh_at = self._cooldown_next_refresh_at(health.last_success_at)

        if next_refresh_at is not None and started_at < next_refresh_at:
            return XRefreshSummary(
                started_at=started_at,
                finished_at=started_at,
                fetched_count=0,
                inserted_count=0,
                error=None,
                latency_ms=0.0,
                skipped=True,
                skip_reason="cooldown_active",
                next_refresh_at=next_refresh_at,
            )

        try:
            by_handle: dict[str, list[dict[str, object]]] = {}
            for account in active_accounts:
                by_handle[account.handle.lower()] = self.provider.get_user_last_tweets(account.handle)
        except (TwitterApiIoError, OSError, json.JSONDecodeError, ValueError) as exc:
            finished_at = _utc_now()
            latency_ms = (finished_at - started_at).total_seconds() * 1000
            _record_fetch_failure(health, finished_at=finished_at, latency_ms=latency_ms, error=str(exc))
            self.session.commit()
            return XRefreshSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_count=0,
                inserted_count=0,
                error=str(exc),
                latency_ms=latency_ms,
                next_refresh_at=next_refresh_at,
            )

        fetched_count = 0
        inserted_count = 0
        inserted_post_rows: list[tuple[object, object, list[str]]] = []

        for account in active_accounts:
            tweets = by_handle.get(account.handle.lower(), [])
            for raw_tweet in tweets:
                summary = _tweet_summary_view(
                    raw_tweet,
                    fallback_handle=account.handle,
                    fallback_name=account.display_name,
                    fallback_market=account.market_focus,
                )
                if summary is None:
                    continue

                fetched_count += 1
                external_post_id = str(raw_tweet.get("id") or _extract_post_id(summary.canonical_url) or "").strip() or None
                dedupe_hash = _dedupe_hash(account.handle, summary.content_text, summary.posted_at)
                if self.posts.exists(
                    canonical_url=summary.canonical_url,
                    external_post_id=external_post_id,
                    dedupe_hash=dedupe_hash,
                ):
                    continue

                post = self.posts.create_post(
                    account_id=account.id,
                    external_post_id=external_post_id,
                    canonical_url=summary.canonical_url,
                    content_text=summary.content_text,
                    market=summary.market,
                    sentiment_label=summary.sentiment_label if summary.sentiment_label in VALID_SENTIMENTS else "unknown",
                    relevance_score=summary.relevance_score,
                    posted_at=summary.posted_at,
                    captured_at=summary.captured_at,
                    raw_payload_json=json.dumps(raw_tweet, ensure_ascii=False),
                    dedupe_hash=dedupe_hash,
                )
                mentions = [{"symbol": symbol, "market": summary.market, "confidence": 0.8} for symbol in summary.symbols]
                self.posts.add_mentions(post.id, mentions)
                inserted_post_rows.append((post, account, summary.symbols))
                inserted_count += 1

        self.signal_builder.build(inserted_post_rows)

        finished_at = _utc_now()
        latency_ms = (finished_at - started_at).total_seconds() * 1000
        _record_fetch_success(health, finished_at=finished_at, latency_ms=latency_ms)
        self.session.commit()
        return XRefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            fetched_count=fetched_count,
            inserted_count=inserted_count,
            error=None,
            latency_ms=latency_ms,
            next_refresh_at=self._cooldown_next_refresh_at(finished_at),
        )

    def search_posts(self, query: str, limit: int) -> list[XPostSummaryView]:
        tweets = self.provider.advanced_search(query=query, limit=limit)
        results: list[XPostSummaryView] = []
        for raw_tweet in tweets:
            summary = _tweet_summary_view(raw_tweet)
            if summary is None:
                continue
            results.append(summary)
        return results

    def provider_health(self) -> tuple[bool, str]:
        if not self.settings.x_monitor_enabled:
            return False, "disabled"
        if not self.provider.configured:
            return False, "not_configured"
        active_accounts = self.accounts.list_refresh_targets()
        if not active_accounts:
            return True, "configured"
        try:
            self.provider.probe_account(active_accounts[0].handle)
        except TwitterApiIoError as exc:
            return False, str(exc)
        return True, "configured"
