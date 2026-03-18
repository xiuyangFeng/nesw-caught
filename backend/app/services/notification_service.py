from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.db.session import SessionLocal
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.repositories.feishu_notify_config_repository import FeishuNotifyConfigRepository
from app.services.feishu_client import (
    FeishuClient,
    FeishuClientError,
    build_alert_card,
    build_analysis_card,
    build_news_batch_card,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self) -> None:
        self._news_buffer: list[dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._watchlist_state: dict[str, bool] = {}
        self._watchlist_state_lock = threading.Lock()
        self._last_batch_time: float = time.time()
        self._scheduler_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_batch_time = time.time()
        self._scheduler_thread = threading.Thread(
            target=self._batch_loop, daemon=True, name="notify-batch"
        )
        self._scheduler_thread.start()
        logger.info("notification batch scheduler started")

    def stop(self) -> None:
        self._running = False

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

        with self._buffer_lock:
            self._news_buffer.append(payload)

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

            card = build_alert_card(
                symbol=symbol,
                display_name=payload.get("display_name", ""),
                price=payload.get("price"),
                change_percent=change_percent,
                threshold=threshold,
            )
            if self._send(config, card):
                self._watchlist_state[symbol] = True

    def on_analysis_completed(self, payload: dict[str, Any]) -> None:
        config = self._load_config()
        if not config or not config.analysis_enabled:
            return

        top_pick = payload.get("top_pick")
        if not top_pick:
            return

        card = build_analysis_card(
            news_title=payload.get("news_title", ""),
            top_pick=top_pick,
            candidates=payload.get("candidates", []),
            summary=payload.get("summary"),
            risk_notes=payload.get("risk_notes"),
        )
        self._send(config, card)

    def _batch_loop(self) -> None:
        while self._running:
            time.sleep(30)
            config = self._load_config()
            if not config or not config.news_enabled:
                with self._buffer_lock:
                    self._news_buffer.clear()
                self._last_batch_time = time.time()
                continue

            interval_seconds = config.news_batch_interval_minutes * 60
            elapsed = time.time() - self._last_batch_time
            if elapsed < interval_seconds:
                continue

            with self._buffer_lock:
                items = list(self._news_buffer)
                self._news_buffer.clear()

            self._last_batch_time = time.time()

            if not items:
                continue

            card = build_news_batch_card(items)
            self._send(config, card)

    def _load_config(self) -> FeishuNotifyConfig | None:
        try:
            with SessionLocal() as session:
                repo = FeishuNotifyConfigRepository(session)
                return repo.get_active()
        except Exception:
            logger.exception("failed to load feishu notify config")
            return None

    def _send(self, config: FeishuNotifyConfig, card: dict[str, Any]) -> bool:
        try:
            client = FeishuClient(app_id=config.app_id, app_secret=config.app_secret)
            client.send_card(
                target_type=config.target_type,
                target_id=config.target_id,
                card=card,
            )
            return True
        except FeishuClientError:
            logger.exception("feishu notification send failed")
        except Exception:
            logger.exception("unexpected error sending feishu notification")
        return False


_instance: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _instance
    if _instance is None:
        _instance = NotificationService()
    return _instance
