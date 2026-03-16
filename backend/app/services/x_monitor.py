from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.x_account_repository import XAccountRepository
from app.repositories.x_post_repository import XPostRepository
from app.repositories.x_source_health_repository import XSourceHealthRepository
from app.services.grok_bridge_client import GrokBridgeClient, GrokBridgeError

VALID_MARKETS = {"hk", "us", "cn"}
VALID_SENTIMENTS = {"positive", "negative", "neutral", "mixed", "unknown"}
PROVIDER_NAME = "grok-bridge"


@dataclass(frozen=True)
class XRefreshSummary:
    started_at: datetime
    finished_at: datetime
    fetched_count: int
    inserted_count: int
    error: str | None
    latency_ms: float


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


def _extract_json_array(raw_text: str) -> list[dict[str, object]]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no json array found in grok response")

    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, list):
        raise ValueError("grok response is not a json array")
    return [item for item in payload if isinstance(item, dict)]


class XMonitorService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.accounts = XAccountRepository(session)
        self.posts = XPostRepository(session)
        self.health_repo = XSourceHealthRepository(session)
        self.bridge = GrokBridgeClient()

    def ensure_enabled(self) -> None:
        if not self.settings.x_monitor_enabled:
            raise ValueError("x monitor is disabled")

    def sync_accounts_from_file(self) -> list:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            return self.accounts.list_all()

        with open(accounts_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        raw_accounts = payload.get("accounts", [])
        if not isinstance(raw_accounts, list):
            raise ValueError("x monitor accounts file must contain an accounts array")

        normalized: list[dict[str, object]] = []
        for item in raw_accounts:
            if not isinstance(item, dict):
                continue
            account_handle = str(item.get("handle") or "").lstrip("@").strip()
            if not account_handle:
                continue
            normalized.append(
                {
                    "handle": account_handle,
                    "display_name": str(item.get("display_name") or account_handle),
                    "market_focus": str(item.get("market_focus")) if item.get("market_focus") else None,
                    "is_active": bool(item.get("is_active", True)),
                    "priority": int(item.get("priority", 0)),
                    "notes": str(item.get("notes")) if item.get("notes") else None,
                }
            )

        accounts = self.accounts.upsert_many(normalized)
        self.session.commit()
        return accounts

    def build_prompt(self, account_handles: list[str]) -> str:
        handles = ", ".join(f"@{handle}" for handle in account_handles)
        return (
            "You are extracting recent X posts for a local market intelligence dashboard. "
            "Only include posts from these whitelisted accounts: "
            f"{handles}. "
            "Only include recent posts relevant to HK equities, US equities, ADRs, China tech, earnings, macro, semiconductors, AI, cloud, or policy. "
            "Return only a JSON array with objects using exactly these keys: "
            "account_handle, account_display_name, post_text, posted_at, url, symbols, market, sentiment_label, relevance_score, reason. "
            "Rules: symbols must be an array of ticker strings or empty array; market must be hk/us/cn; sentiment_label must be positive/negative/neutral/mixed/unknown; "
            "posted_at should be ISO 8601 when known; url should be the original X post URL when known; relevance_score should be 0 to 1. "
            "Do not include markdown, prose, comments, or any wrapper object."
        )

    def refresh(self) -> XRefreshSummary:
        self.ensure_enabled()
        self.sync_accounts_from_file()

        active_accounts = self.accounts.list_active()
        started_at = _utc_now()
        health = self.health_repo.get_or_create(PROVIDER_NAME)

        if not active_accounts:
            finished_at = _utc_now()
            health.total_fetches += 1
            health.last_success_at = finished_at
            health.consecutive_failures = 0
            self.session.commit()
            return XRefreshSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_count=0,
                inserted_count=0,
                error=None,
                latency_ms=(finished_at - started_at).total_seconds() * 1000,
            )

        try:
            raw_text = self.bridge.chat(self.build_prompt([account.handle for account in active_accounts]))
            rows = _extract_json_array(raw_text)
        except (GrokBridgeError, ValueError, OSError, json.JSONDecodeError) as exc:
            finished_at = _utc_now()
            latency_ms = (finished_at - started_at).total_seconds() * 1000
            health.total_fetches += 1
            health.total_failures += 1
            health.consecutive_failures += 1
            health.last_failure_at = finished_at
            health.last_error = str(exc)
            if health.avg_latency_ms is None:
                health.avg_latency_ms = latency_ms
            else:
                health.avg_latency_ms = ((health.avg_latency_ms * (health.total_fetches - 1)) + latency_ms) / health.total_fetches
            self.session.commit()
            return XRefreshSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_count=0,
                inserted_count=0,
                error=str(exc),
                latency_ms=latency_ms,
            )

        fetched_count = 0
        inserted_count = 0
        by_handle = {account.handle.lower(): account for account in active_accounts}
        captured_at = _utc_now()

        for row in rows:
            account_handle = str(row.get("account_handle") or "").lstrip("@").strip().lower()
            content_text = str(row.get("post_text") or "").strip()
            if not account_handle or not content_text:
                continue

            account = by_handle.get(account_handle)
            if account is None:
                continue

            fetched_count += 1
            posted_at = _parse_datetime(str(row.get("posted_at") or "")) if row.get("posted_at") else None
            canonical_url = str(row.get("url") or "").strip() or None
            external_post_id = _extract_post_id(canonical_url)
            market = str(row.get("market") or "us").lower()
            if market not in VALID_MARKETS:
                market = "us"
            sentiment_label = str(row.get("sentiment_label") or "unknown").lower()
            if sentiment_label not in VALID_SENTIMENTS:
                sentiment_label = "unknown"

            relevance_score = None
            if row.get("relevance_score") is not None:
                try:
                    relevance_score = max(0.0, min(1.0, float(row["relevance_score"])))
                except (TypeError, ValueError):
                    relevance_score = None

            dedupe_hash = _dedupe_hash(account.handle, content_text, posted_at)
            if self.posts.exists(
                canonical_url=canonical_url,
                external_post_id=external_post_id,
                dedupe_hash=dedupe_hash,
            ):
                continue

            post = self.posts.create_post(
                account_id=account.id,
                external_post_id=external_post_id,
                canonical_url=canonical_url,
                content_text=content_text,
                market=market,
                sentiment_label=sentiment_label,
                relevance_score=relevance_score,
                posted_at=posted_at,
                captured_at=captured_at,
                raw_payload_json=json.dumps(row, ensure_ascii=False),
                dedupe_hash=dedupe_hash,
            )

            symbols = row.get("symbols") if isinstance(row.get("symbols"), list) else []
            mentions: list[dict[str, object]] = []
            for symbol in symbols:
                normalized_symbol = str(symbol).upper().strip()
                if not normalized_symbol:
                    continue
                mentions.append({"symbol": normalized_symbol, "market": market, "confidence": 0.8})
            self.posts.add_mentions(post.id, mentions)
            inserted_count += 1

        finished_at = _utc_now()
        latency_ms = (finished_at - started_at).total_seconds() * 1000
        health.total_fetches += 1
        health.last_success_at = finished_at
        health.consecutive_failures = 0
        health.last_error = None
        if health.avg_latency_ms is None:
            health.avg_latency_ms = latency_ms
        else:
            health.avg_latency_ms = ((health.avg_latency_ms * (health.total_fetches - 1)) + latency_ms) / health.total_fetches
        self.session.commit()
        return XRefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            fetched_count=fetched_count,
            inserted_count=inserted_count,
            error=None,
            latency_ms=latency_ms,
        )

    def bridge_health(self) -> tuple[bool, str]:
        if not self.settings.x_monitor_enabled:
            return False, "disabled"
        if not self.bridge.configured:
            return False, "not_configured"
        try:
            health = self.bridge.health()
        except GrokBridgeError as exc:
            return False, str(exc)
        status = health.status
        if health.url:
            parsed = urlparse(health.url)
            if parsed.netloc:
                status = f"{status}:{parsed.netloc}"
        return True, status
