from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.session import SessionLocal
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.repositories.feishu_notify_config_repository import FeishuNotifyConfigRepository
from app.repositories.notification_job_repository import NotificationJobRepository
from app.services.feishu_client import (
    FeishuClientError,
    build_alert_card,
    build_analysis_card,
    build_news_batch_card,
    get_shared_feishu_sender,
)

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 5
RETRY_DELAYS_SECONDS = (30, 120, 300, 900, 1800)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationService:
    def __init__(
        self,
        *,
        poll_interval_seconds: int = 30,
        lease_seconds: int = 300,
    ) -> None:
        self._watchlist_state: dict[str, bool] = {}
        self._watchlist_state_lock = threading.Lock()
        self._poll_interval_seconds = poll_interval_seconds
        self._lease_seconds = lease_seconds
        self._delivery_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._delivery_thread = threading.Thread(
            target=self._delivery_loop, daemon=True, name="notify-delivery"
        )
        self._delivery_thread.start()
        logger.info("notification delivery scheduler started")

    def stop(self) -> None:
        self._running = False
        thread = self._delivery_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def on_news_created(self, payload: dict[str, Any]) -> None:
        config = self._load_config()
        if not config or not config.news_enabled:
            return

        if config.news_keywords:
            keywords = [k.strip().lower() for k in config.news_keywords.split(",") if k.strip()]
            title = (payload.get("title") or "").lower()
            summary = (payload.get("summary") or "").lower()
            text = f"{title} {summary}"
            if not any(kw in text for kw in keywords):
                return

        dedupe_key = self._build_news_source_dedupe_key(payload)
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.enqueue_source_event(payload=payload, dedupe_key=dedupe_key)

    def on_watchlist_alert(self, payload: dict[str, Any]) -> None:
        symbol = payload.get("symbol")
        threshold = payload.get("alert_threshold")
        change_percent = payload.get("change_percent")
        if not symbol or threshold is None:
            return

        is_above_threshold = change_percent is not None and abs(change_percent) >= threshold
        with self._watchlist_state_lock:
            was_above_threshold = self._watchlist_state.get(symbol, False)
            if not is_above_threshold:
                self._watchlist_state.pop(symbol, None)
                return
            if was_above_threshold:
                return
            config = self._load_config()
            if not config or not config.alert_enabled:
                return

            with SessionLocal() as session:
                repo = NotificationJobRepository(session)
                repo.enqueue(
                    channel="feishu",
                    event_type="watchlist_alert",
                    payload=payload,
                )
            self._watchlist_state[symbol] = True

    def on_analysis_completed(self, payload: dict[str, Any]) -> None:
        config = self._load_config()
        if not config or not config.analysis_enabled:
            return

        top_pick = payload.get("top_pick")
        if not top_pick:
            return

        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.enqueue(
                channel="feishu",
                event_type="analysis_result",
                payload=payload,
            )

    def _delivery_loop(self) -> None:
        while self._running:
            self._delivery_tick()
            time.sleep(self._poll_interval_seconds)

    def _delivery_tick(self, *, now: datetime | None = None) -> None:
        config = self._load_config()
        if not config:
            return

        current_time = now or _utc_now()
        if config.news_enabled:
            self._materialize_news_batch_jobs(config, now=current_time)
        else:
            self._discard_pending_news_jobs()

        for _ in range(50):
            with SessionLocal() as session:
                repo = NotificationJobRepository(session)
                job = repo.claim_next_ready(
                    channel="feishu",
                    lease_seconds=self._lease_seconds,
                    now=current_time,
                )
            if job is None:
                return
            self._deliver_job(config=config, job=job, now=current_time)

    def _materialize_news_batch_jobs(self, config: FeishuNotifyConfig, *, now: datetime) -> None:
        cutoff = now - timedelta(minutes=config.news_batch_interval_minutes)
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            due_source_events = [
                job
                for job in repo.list_pending(channel="news", event_type="news_source_event", now=now, limit=200)
                if job.created_at <= cutoff
            ]
            if not due_source_events:
                return

            items = [json.loads(job.payload_json) for job in due_source_events]
            dedupe_key = self._build_news_batch_dedupe_key(due_source_events)
            repo.enqueue(
                channel="feishu",
                event_type="news_batch",
                payload={"items": items},
                dedupe_key=dedupe_key,
            )
            for job in due_source_events:
                repo.mark_sent(job.id, sent_at=now, lease_token=job.lease_token)

    def _discard_pending_news_jobs(self) -> None:
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.discard_pending(channel="news", event_type="news_source_event")
            repo.discard_pending(channel="feishu", event_type="news_batch")

    def _load_config(self) -> FeishuNotifyConfig | None:
        try:
            with SessionLocal() as session:
                repo = FeishuNotifyConfigRepository(session)
                return repo.get_active()
        except Exception:
            logger.exception("failed to load feishu notify config")
            return None

    def _deliver_job(self, *, config: FeishuNotifyConfig, job: Any, now: datetime) -> None:
        card = self._build_card_for_job(job)
        if card is None:
            with SessionLocal() as session:
                NotificationJobRepository(session).mark_failed(
                    job.id,
                    error=f"unsupported event_type: {job.event_type}",
                    lease_token=getattr(job, "lease_token", None),
                )
            return

        sender = get_shared_feishu_sender(app_id=config.app_id, app_secret=config.app_secret)
        try:
            sender.send_card(
                target_type=config.target_type,
                target_id=config.target_id,
                card=card,
            )
            with SessionLocal() as session:
                NotificationJobRepository(session).mark_sent(
                    job.id,
                    sent_at=now,
                    lease_token=getattr(job, "lease_token", None),
                )
        except FeishuClientError as exc:
            logger.exception("feishu notification send failed")
            self._mark_failure(job=job, error=str(exc), retryable=exc.retryable, now=now)
        except Exception:
            logger.exception("unexpected error sending feishu notification")
            self._mark_failure(job=job, error="unexpected send error", retryable=True, now=now)

    def _mark_failure(self, *, job: Any, error: str, retryable: bool, now: datetime) -> None:
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            if retryable and job.attempt_count < MAX_RETRY_ATTEMPTS:
                repo.mark_retryable_failure(
                    job.id,
                    error=error,
                    next_retry_at=now + timedelta(seconds=self._retry_delay_seconds(job.attempt_count)),
                    lease_token=getattr(job, "lease_token", None),
                )
                if job.event_type == "watchlist_alert":
                    return
                return
            repo.mark_failed(job.id, error=error, lease_token=getattr(job, "lease_token", None))
        if job.event_type == "watchlist_alert":
            self._release_watchlist_state(job)

    def _build_card_for_job(self, job: Any) -> dict[str, Any] | None:
        payload = json.loads(job.payload_json)
        if job.event_type == "news_batch":
            return build_news_batch_card(payload.get("items", []))
        if job.event_type == "watchlist_alert":
            return build_alert_card(
                symbol=payload.get("symbol", ""),
                display_name=payload.get("display_name", ""),
                price=payload.get("price"),
                change_percent=payload.get("change_percent"),
                threshold=payload.get("alert_threshold"),
            )
        if job.event_type == "analysis_result":
            return build_analysis_card(
                news_title=payload.get("news_title", ""),
                top_pick=payload.get("top_pick"),
                candidates=payload.get("candidates", []),
                summary=payload.get("summary"),
                risk_notes=payload.get("risk_notes"),
            )
        return None

    def _retry_delay_seconds(self, attempt_count: int) -> int:
        index = max(0, min(attempt_count - 1, len(RETRY_DELAYS_SECONDS) - 1))
        return RETRY_DELAYS_SECONDS[index]

    def _build_news_source_dedupe_key(self, payload: dict[str, Any]) -> str | None:
        parts = [
            str(payload.get("source_name") or "").strip().lower(),
            str(payload.get("title") or "").strip().lower(),
            str(payload.get("published_at") or "").strip().lower(),
        ]
        if not any(parts):
            return None
        return "news-source:" + "|".join(parts)

    def _build_news_batch_dedupe_key(self, jobs: list[Any]) -> str:
        return "news-batch:" + ",".join(str(job.id) for job in jobs)

    def _release_watchlist_state(self, job: Any) -> None:
        payload = json.loads(job.payload_json)
        symbol = payload.get("symbol")
        if not symbol:
            return
        with self._watchlist_state_lock:
            self._watchlist_state.pop(str(symbol), None)


_instance: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _instance
    if _instance is None:
        _instance = NotificationService()
    return _instance
