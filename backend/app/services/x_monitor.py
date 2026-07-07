from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.x_account_repository import XAccountRepository
from app.repositories.x_post_repository import XPostRepository
from app.repositories.x_signal_repository import XSignalRepository
from app.repositories.x_source_health_repository import XSourceHealthRepository
from app.schemas.x_monitor import XPostSummaryView, XRadarMacroClusterView, XRadarResponse, XRadarSignalView
from app.services.twitterapi_io_client import TwitterApiIoClient, TwitterApiIoError
from app.services.x_radar_signal_builder import XRadarSignalBuilder

VALID_MARKETS = {"hk", "us", "cn"}
VALID_SENTIMENTS = {"positive", "negative", "neutral", "mixed", "unknown"}
VALID_TIERS = {"core", "watch", "muted"}
PROVIDER_NAME = "twitterapi.io"


class XMonitorError(ValueError):
    """Base domain error for the X monitor feature (maps to HTTP 400 by default)."""


class XMonitorDisabledError(XMonitorError):
    """Raised when the feature flag is off (maps to HTTP 503)."""


class XAccountNotFoundError(XMonitorError):
    """Raised when a tracked account does not exist (maps to HTTP 404)."""


class XAccountAlreadyExistsError(XMonitorError):
    """Raised when creating a tracked account that already exists (maps to HTTP 409)."""


@dataclass(frozen=True)
class XRefreshSummary:
    started_at: datetime
    finished_at: datetime
    fetched_count: int
    inserted_count: int
    error: str | None
    latency_ms: float
    skipped: bool = False
    skip_reason: str | None = None
    next_refresh_at: datetime | None = None


@dataclass(frozen=True)
class XAccountsImportSummary:
    created_count: int
    updated_count: int
    skipped_count: int


@dataclass(frozen=True)
class XAccountsExportSummary:
    exported_count: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(normalized))
    except ValueError:
        try:
            return _normalize_datetime(parsedate_to_datetime(value.strip()))
        except (TypeError, ValueError, IndexError):
            return None


def _extract_post_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def _normalize_content(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _posted_hour_bucket(posted_at: datetime | None) -> str:
    if posted_at is None:
        return "unknown"
    normalized = _normalize_datetime(posted_at)
    return normalized.strftime("%Y-%m-%dT%H")


def _dedupe_hash(handle: str, content_text: str, posted_at: datetime | None) -> str:
    material = f"{handle.lower()}|{_normalize_content(content_text)}|{_posted_hour_bucket(posted_at)}"
    return sha256(material.encode("utf-8")).hexdigest()


def _extract_symbols(raw_tweet: dict[str, object]) -> list[str]:
    raw_symbols = raw_tweet.get("symbols")
    if isinstance(raw_symbols, list):
        return [str(item).upper().strip() for item in raw_symbols if str(item).strip()]

    content_text = str(raw_tweet.get("text") or "")
    cashtags = re.findall(r"\$([A-Za-z][A-Za-z0-9._-]{0,9})", content_text)
    seen: list[str] = []
    for symbol in cashtags:
        normalized = symbol.upper().strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _infer_market(symbols: list[str], default_market: str | None = None) -> str:
    if default_market in VALID_MARKETS:
        return str(default_market)
    for symbol in symbols:
        if symbol.endswith(".HK") or symbol.startswith("HK"):
            return "hk"
    return "us"


def _extract_author_handle(raw_tweet: dict[str, object]) -> str:
    author = raw_tweet.get("author")
    if isinstance(author, dict):
        handle = str(author.get("userName") or author.get("screen_name") or "").lstrip("@").strip()
        if handle:
            return handle
    return str(raw_tweet.get("userName") or "").lstrip("@").strip()


def _extract_author_name(raw_tweet: dict[str, object], fallback_handle: str) -> str:
    author = raw_tweet.get("author")
    if isinstance(author, dict):
        name = str(author.get("name") or "").strip()
        if name:
            return name
    return fallback_handle


def _normalize_handle(value: str) -> str:
    return value.lstrip("@").strip()


def _ensure_enabled(settings) -> None:
    if not settings.x_monitor_enabled:
        raise XMonitorDisabledError("x monitor is disabled")


def _normalize_account_row(item: object) -> dict[str, object] | None:
    """Normalize one raw accounts-file entry into a repository payload.

    Returns None when the entry is not a dict or has no usable handle.
    Unknown tiers fall back to "watch".
    """
    if not isinstance(item, dict):
        return None
    handle = _normalize_handle(str(item.get("handle") or ""))
    if not handle:
        return None
    tier = str(item.get("tier") or "watch").strip().lower()
    if tier not in VALID_TIERS:
        tier = "watch"
    return {
        "handle": handle,
        "display_name": str(item.get("display_name") or handle),
        "market_focus": str(item.get("market_focus")) if item.get("market_focus") else None,
        "is_active": bool(item.get("is_active", True)),
        "priority": int(item.get("priority", 0)),
        "tier": tier,
        "source": "file_import",
        "notes": str(item.get("notes")) if item.get("notes") else None,
    }


def _update_avg_latency(health, latency_ms: float) -> None:
    """Fold one fetch latency into the running weighted average.

    Assumes health.total_fetches has already been incremented for this fetch.
    """
    if health.avg_latency_ms is None:
        health.avg_latency_ms = latency_ms
    else:
        health.avg_latency_ms = ((health.avg_latency_ms * (health.total_fetches - 1)) + latency_ms) / health.total_fetches


def _record_fetch_success(health, *, finished_at: datetime, latency_ms: float) -> None:
    health.total_fetches += 1
    health.last_success_at = finished_at
    health.consecutive_failures = 0
    health.last_error = None
    _update_avg_latency(health, latency_ms)


def _record_fetch_failure(health, *, finished_at: datetime, latency_ms: float, error: str) -> None:
    health.total_fetches += 1
    health.total_failures += 1
    health.consecutive_failures += 1
    health.last_failure_at = finished_at
    health.last_error = error
    _update_avg_latency(health, latency_ms)


def _tweet_summary_view(
    raw_tweet: dict[str, object],
    *,
    fallback_handle: str | None = None,
    fallback_name: str | None = None,
    fallback_market: str | None = None,
) -> XPostSummaryView | None:
    """Normalize one raw provider tweet into a summary view (None when unusable)."""
    account_handle = _extract_author_handle(raw_tweet) or str(fallback_handle or "").strip()
    content_text = str(raw_tweet.get("text") or raw_tweet.get("fullText") or "").strip()
    if not account_handle or not content_text:
        return None

    symbols = _extract_symbols(raw_tweet)
    posted_at = _parse_datetime(str(raw_tweet.get("createdAt") or raw_tweet.get("created_at") or ""))
    canonical_url = str(raw_tweet.get("url") or "").strip() or None
    market = _infer_market(symbols, fallback_market)

    return XPostSummaryView(
        id=0,
        account_handle=account_handle,
        account_display_name=_extract_author_name(raw_tweet, fallback_name or account_handle),
        content_text=content_text,
        canonical_url=canonical_url,
        market=market,
        sentiment_label="unknown",
        relevance_score=None,
        posted_at=posted_at,
        captured_at=_utc_now(),
        symbols=symbols,
    )


class XAccountManager:
    """Tracked-account administration: CRUD plus JSON file import/export/sync."""

    def __init__(self, session: Session, settings, accounts: XAccountRepository) -> None:
        self.session = session
        self.settings = settings
        self.accounts = accounts

    def list_accounts(self) -> list:
        return self.accounts.list_all()

    def _get_required(self, handle: str):
        instance = self.accounts.get_by_handle(handle)
        if instance is None:
            raise XAccountNotFoundError(f"x account not found: {handle}")
        return instance

    def create_account(self, payload) -> object:
        handle = _normalize_handle(payload.handle)
        if self.accounts.get_by_handle(handle) is not None:
            raise XAccountAlreadyExistsError(f"x account already exists: {handle}")
        account = self.accounts.create(
            {
                "handle": handle,
                "display_name": payload.display_name.strip(),
                "market_focus": payload.market_focus,
                "is_active": payload.is_active,
                "priority": payload.priority,
                "tier": payload.tier,
                "source": "manual",
                "notes": payload.notes,
            }
        )
        self.session.commit()
        return account

    def update_account(self, handle: str, payload) -> object:
        instance = self._get_required(handle)
        account = self.accounts.update(
            instance,
            {
                "display_name": payload.display_name,
                "market_focus": payload.market_focus,
                "is_active": payload.is_active,
                "priority": payload.priority,
                "tier": payload.tier,
                "notes": payload.notes,
            },
        )
        self.session.commit()
        return account

    def delete_account(self, handle: str) -> None:
        instance = self._get_required(handle)
        self.accounts.delete(instance)
        self.session.commit()

    def _read_account_entries(self, accounts_file: str) -> list[object]:
        with open(accounts_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        raw_accounts = payload.get("accounts", [])
        if not isinstance(raw_accounts, list):
            raise XMonitorError("x monitor accounts file must contain an accounts array")
        return raw_accounts

    def sync_accounts_from_file(self) -> list:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            return self.accounts.list_all()

        normalized = [
            row
            for row in (_normalize_account_row(item) for item in self._read_account_entries(accounts_file))
            if row is not None
        ]
        return self.accounts.upsert_many(normalized)

    def import_accounts_from_file(self) -> XAccountsImportSummary:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            raise XMonitorError("x monitor accounts file is not configured")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in self._read_account_entries(accounts_file):
            payload_row = _normalize_account_row(item)
            if payload_row is None:
                skipped_count += 1
                continue
            existing = self.accounts.get_by_handle(str(payload_row["handle"]))
            if existing is None:
                self.accounts.create(payload_row)
                created_count += 1
            else:
                self.accounts.update(existing, payload_row)
                updated_count += 1

        self.session.commit()
        return XAccountsImportSummary(
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
        )

    def export_accounts_to_file(self) -> XAccountsExportSummary:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            raise XMonitorError("x monitor accounts file is not configured")

        payload = {
            "accounts": [
                {
                    "handle": account.handle,
                    "display_name": account.display_name,
                    "market_focus": account.market_focus,
                    "is_active": account.is_active,
                    "priority": account.priority,
                    "tier": account.tier,
                    "source": account.source,
                    "notes": account.notes,
                }
                for account in self.accounts.list_all()
            ]
        }
        with open(accounts_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return XAccountsExportSummary(exported_count=len(payload["accounts"]))


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


class XMonitorService:
    """Aggregating facade over account administration, the fetch pipeline, and read views.

    Keeps the constructor signature and public surface stable for routes,
    the health endpoint, and background callers.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.accounts = XAccountRepository(session)
        self.posts = XPostRepository(session)
        self.signals = XSignalRepository(session)
        self.health_repo = XSourceHealthRepository(session)
        self.provider = TwitterApiIoClient()
        self.signal_builder = XRadarSignalBuilder(
            self.signals,
            rules_file=getattr(self.settings, "x_radar_rules_file", None),
        )
        self.account_manager = XAccountManager(session, self.settings, self.accounts)
        self.pipeline = XFetchPipeline(
            session,
            self.settings,
            accounts=self.accounts,
            posts=self.posts,
            health_repo=self.health_repo,
            provider=self.provider,
            signal_builder=self.signal_builder,
        )

    def ensure_enabled(self) -> None:
        _ensure_enabled(self.settings)

    # -- account administration ------------------------------------------------

    def list_accounts(self) -> list:
        return self.account_manager.list_accounts()

    def sync_accounts_from_file(self) -> list:
        return self.account_manager.sync_accounts_from_file()

    def create_account(self, payload) -> object:
        return self.account_manager.create_account(payload)

    def update_account(self, handle: str, payload) -> object:
        return self.account_manager.update_account(handle, payload)

    def delete_account(self, handle: str) -> None:
        self.account_manager.delete_account(handle)

    def import_accounts_from_file(self) -> XAccountsImportSummary:
        return self.account_manager.import_accounts_from_file()

    def export_accounts_to_file(self) -> XAccountsExportSummary:
        return self.account_manager.export_accounts_to_file()

    # -- fetch pipeline ----------------------------------------------------------

    def refresh(self) -> XRefreshSummary:
        return self.pipeline.refresh()

    def search_posts(self, query: str, limit: int) -> list[XPostSummaryView]:
        return self.pipeline.search_posts(query, limit)

    def provider_health(self) -> tuple[bool, str]:
        return self.pipeline.provider_health()

    # -- read views ---------------------------------------------------------------

    def list_posts(
        self,
        *,
        account_handle: str | None = None,
        symbol: str | None = None,
        market: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[XPostSummaryView]:
        rows = self.posts.list_posts(
            account_handle=account_handle,
            symbol=symbol,
            market=market,
            query=query,
            limit=limit,
        )
        return [XPostSummaryView.from_post(post, account, symbols) for post, account, symbols in rows]

    def get_radar(self, limit: int = 50) -> XRadarResponse:
        return XRadarResponse(
            priority_signals=[
                XRadarSignalView.from_signal(signal)
                for signal in self.signals.list_priority_signals(limit=limit)
            ],
            macro_clusters=[
                XRadarMacroClusterView.model_validate(row)
                for row in self.signals.list_macro_clusters(limit=limit)
            ],
            evidence_stream=[
                XPostSummaryView.from_post(post, account, symbols)
                for post, account, symbols in self.signals.list_evidence_posts(limit=limit)
            ],
        )
