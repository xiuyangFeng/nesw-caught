from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.repositories.feishu_notify_config_repository import FeishuNotifyConfigRepository
from app.repositories.notification_job_repository import NotificationJobRepository
from app.services.feishu_client import (
    FeishuClientError,
    build_alert_card,
    build_alert_digest_card,
    build_analysis_card,
    build_digest_card,
    build_news_batch_card,
    build_sentiment_divergence_card,
    get_shared_feishu_sender,
)

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 5
RETRY_DELAYS_SECONDS = (30, 120, 300, 900, 1800)

# 告警治理严重度：critical 不受免打扰 / 合并限制，其余按策略暂缓或合并。
SEVERITY_CRITICAL = "critical"
SEVERITY_NORMAL = "normal"
SEVERITY_LOW = "low"

# 情绪-价格背离提醒去重锚定的时区：与 sentiment_timeline.py 的自然日聚合口径
# 保持一致（面向中文用户的"今天"），避免同一天内被反复入队刷屏。
_SENTIMENT_DIVERGENCE_DEDUPE_TZ = ZoneInfo("Asia/Shanghai")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class GovernanceConfig:
    """一次治理决策所用的有效配置快照（settings 默认叠加内存覆盖后的结果）。"""

    quiet_hours_start: str | None
    quiet_hours_end: str | None
    quiet_hours_tz: str
    dedupe_window_minutes: int
    digest_window_minutes: int
    digest_threshold: int
    critical_change_percent: float


# 允许通过前端 / 测试覆盖的治理字段白名单。
_GOVERNANCE_KEYS = (
    "quiet_hours_start",
    "quiet_hours_end",
    "quiet_hours_tz",
    "dedupe_window_minutes",
    "digest_window_minutes",
    "digest_threshold",
    "critical_change_percent",
)


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
        self._worker: Any = None
        # 情绪-价格背离周期检查 worker：仅在 settings.sentiment_divergence_alert_enabled
        # 时由 start() 惰性创建/启动；默认 None，零行为变化。
        self._divergence_worker: Any = None
        # 告警治理：内存态运行期覆盖（不落库），叠加在 settings 默认之上。
        self._governance_override: dict[str, Any] = {}
        # 去重窗口用的"同 symbol 最近一次入队时间"，仅内存保存。
        self._recent_alerts: dict[str, datetime] = {}
        # 可注入时钟：测试注固定时间；生产用 UTC now。
        self._now_provider: Callable[[], datetime] = _utc_now

    # ------------------------------------------------------------------
    # 告警治理配置：settings 默认 + 内存覆盖
    # ------------------------------------------------------------------
    def _governance(self) -> GovernanceConfig:
        settings = get_settings()
        values: dict[str, Any] = {
            "quiet_hours_start": settings.notify_quiet_hours_start,
            "quiet_hours_end": settings.notify_quiet_hours_end,
            "quiet_hours_tz": settings.notify_quiet_hours_tz,
            "dedupe_window_minutes": settings.notify_dedupe_window_minutes,
            "digest_window_minutes": settings.notify_digest_window_minutes,
            "digest_threshold": settings.notify_digest_threshold,
            "critical_change_percent": settings.notify_critical_change_percent,
        }
        values.update(self._governance_override)
        for key in ("quiet_hours_start", "quiet_hours_end"):
            candidate = values.get(key)
            if isinstance(candidate, str) and not candidate.strip():
                values[key] = None
        return GovernanceConfig(**values)

    def configure_governance(self, **kwargs: Any) -> None:
        """设置内存态治理覆盖（测试注入 / 前端保存均走这里）。"""
        for key, value in kwargs.items():
            if key not in _GOVERNANCE_KEYS:
                raise ValueError(f"unknown governance field: {key}")
            self._governance_override[key] = value

    def apply_governance(self, payload: dict[str, Any]) -> None:
        """从 API 请求体应用治理覆盖：空串按"未设置"处理。"""
        normalized: dict[str, Any] = {}
        for key in _GOVERNANCE_KEYS:
            if key not in payload:
                continue
            value = payload[key]
            if key in ("quiet_hours_start", "quiet_hours_end", "quiet_hours_tz"):
                if isinstance(value, str) and not value.strip():
                    if key == "quiet_hours_tz":
                        continue  # 时区留空则回落 settings 默认
                    value = None
            normalized[key] = value
        self.configure_governance(**normalized)

    def governance_view(self) -> dict[str, Any]:
        """返回当前有效治理配置，供 API 回显。"""
        gov = self._governance()
        return {
            "quiet_hours_start": gov.quiet_hours_start,
            "quiet_hours_end": gov.quiet_hours_end,
            "quiet_hours_tz": gov.quiet_hours_tz,
            "dedupe_window_minutes": gov.dedupe_window_minutes,
            "digest_window_minutes": gov.digest_window_minutes,
            "digest_threshold": gov.digest_threshold,
            "critical_change_percent": gov.critical_change_percent,
        }

    def _classify_severity(self, event_type: str, payload: dict[str, Any]) -> str:
        """按事件类型 / 触发条件打严重度：critical / normal / low。"""
        if event_type == "watchlist_alert":
            gov = self._governance()
            change = payload.get("change_percent")
            if change is not None and abs(change) >= gov.critical_change_percent:
                return SEVERITY_CRITICAL
            return SEVERITY_NORMAL
        if event_type in ("analysis_result", "alert_digest", "sentiment_divergence"):
            return SEVERITY_NORMAL
        return SEVERITY_LOW

    def start(self) -> None:
        if self._worker is None:
            from app.workers.notification_delivery_worker import NotificationDeliveryWorker
            self._worker = NotificationDeliveryWorker(
                session_factory=SessionLocal,
                notification_service=self,
                poll_interval_seconds=self._poll_interval_seconds,
            )
            self._worker.start()
            logger.info("notification delivery scheduler started")

        # 情绪-价格背离周期检查：main.py 的 lifespan 无条件调用 start()/stop()，
        # 这里按 settings 开关惰性决定要不要再起一个 worker——既复用了既有的
        # "web 进程随 lifespan 启停后台 worker" 注册点，又不需要改 main.py，
        # 关闭时（默认）完全不创建、零行为变化。
        if self._divergence_worker is None and get_settings().sentiment_divergence_alert_enabled:
            from app.workers.queue_worker import SentimentDivergenceAlertWorker
            self._divergence_worker = SentimentDivergenceAlertWorker(
                session_factory=SessionLocal,
                notification_service=self,
            )
            self._divergence_worker.start()
            logger.info("sentiment divergence alert worker started")

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        if self._divergence_worker is not None:
            self._divergence_worker.stop()
            self._divergence_worker = None

    def on_news_created(self, payload: dict[str, Any]) -> None:
        config = self._load_config()
        if not config or not config.news_enabled:
            return

        if not self._matches_news_keywords(config, payload):
            return

        dedupe_key = self._build_news_source_dedupe_key(payload)
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.enqueue_source_event(payload=payload, dedupe_key=dedupe_key)
            session.commit()

    def on_news_created_batch(self, payloads: list[dict[str, Any]]) -> None:
        """批量入队新闻源事件：一次配置加载 + 批量 enqueue + 一次提交。

        与单条 on_news_created 的过滤 / 去重语义一致，但避免逐条开关 session。
        """
        if not payloads:
            return
        config = self._load_config()
        if not config or not config.news_enabled:
            return

        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            for payload in payloads:
                if not self._matches_news_keywords(config, payload):
                    continue
                dedupe_key = self._build_news_source_dedupe_key(payload)
                repo.enqueue_source_event(payload=payload, dedupe_key=dedupe_key)
            session.commit()

    @staticmethod
    def _matches_news_keywords(config: FeishuNotifyConfig, payload: dict[str, Any]) -> bool:
        if not config.news_keywords:
            return True
        keywords = [k.strip().lower() for k in config.news_keywords.split(",") if k.strip()]
        title = (payload.get("title") or "").lower()
        summary = (payload.get("summary") or "").lower()
        text = f"{title} {summary}"
        return any(kw in text for kw in keywords)

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

            gov = self._governance()
            now = self._now_provider()
            # 去重窗口：同 symbol 在 N 分钟内已入队过则抑制（0 = 关闭）。
            if gov.dedupe_window_minutes > 0:
                last_enqueued_at = self._recent_alerts.get(str(symbol))
                if (
                    last_enqueued_at is not None
                    and now - last_enqueued_at < timedelta(minutes=gov.dedupe_window_minutes)
                ):
                    self._watchlist_state[symbol] = True
                    return

            # 合并摘要：非 critical 告警先暂存一个合并窗口再合并（0 = 关闭，立即发）。
            severity = self._classify_severity("watchlist_alert", payload)
            next_retry_at = None
            if severity != SEVERITY_CRITICAL and gov.digest_window_minutes > 0:
                next_retry_at = now + timedelta(minutes=gov.digest_window_minutes)

            with SessionLocal() as session:
                repo = NotificationJobRepository(session)
                repo.enqueue(
                    channel="feishu",
                    event_type="watchlist_alert",
                    payload=payload,
                    next_retry_at=next_retry_at,
                )
                session.commit()
            self._recent_alerts[str(symbol)] = now
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
            session.commit()

    def on_sentiment_divergence_detected(self, payload: dict[str, Any]) -> None:
        """情绪-价格背离命中入队：与 `on_digest_ready` 同构——功能自身的启用开关

        （`settings.sentiment_divergence_alert_enabled`）由调用方（周期 worker 是否
        存在）把关，这里只再确认"有没有活跃飞书目的地"，不额外叠加 `alert_enabled`
        （那是自选股涨跌幅告警自己的开关，与背离提醒是两个功能）。
        """
        symbol = payload.get("symbol")
        status_value = payload.get("status")
        if not symbol or not status_value:
            return

        config = self._load_config()
        if not config:
            return

        dedupe_key = self._build_sentiment_divergence_dedupe_key(payload)
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.enqueue(
                channel="feishu",
                event_type="sentiment_divergence",
                payload=payload,
                dedupe_key=dedupe_key,
            )
            session.commit()

    def on_digest_ready(self, payload: dict[str, Any]) -> None:
        # 无活跃飞书配置时不入队（无处可推）；与其他事件同构地依赖 get_active 门控。
        config = self._load_config()
        if not config:
            return
        if not payload.get("sections"):
            return

        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.enqueue(
                channel="feishu",
                event_type="digest",
                payload=payload,
            )
            session.commit()

    def _delivery_tick(self, *, now: datetime | None = None) -> int:
        config = self._load_config()
        if not config:
            return 0

        current_time = now or self._now_provider()
        gov = self._governance()
        if config.news_enabled:
            self._materialize_news_batch_jobs(config, now=current_time)
        else:
            self._discard_pending_news_jobs()

        # 治理层：先把到期的暂存告警合并为摘要，再对免打扰时段做暂缓。
        self._materialize_alert_digest_jobs(now=current_time, gov=gov)
        self._apply_quiet_hours(now=current_time, gov=gov)

        processed_count = 0
        for _ in range(50):
            with SessionLocal() as session:
                repo = NotificationJobRepository(session)
                job = repo.claim_next_ready(
                    channel="feishu",
                    lease_seconds=self._lease_seconds,
                    now=current_time,
                )
                # 租约必须在慢速外部发送开始前落库。
                session.commit()
            if job is None:
                break
            self._deliver_job(config=config, job=job, now=current_time)
            processed_count += 1
        return processed_count

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
            # 批次落库与源事件标记在同一事务内提交。
            session.commit()

    def _discard_pending_news_jobs(self) -> None:
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            repo.discard_pending(channel="news", event_type="news_source_event")
            repo.discard_pending(channel="feishu", event_type="news_batch")
            session.commit()

    def _materialize_alert_digest_jobs(self, *, now: datetime, gov: GovernanceConfig) -> None:
        """把暂存到期的多条自选股异动合并成一条摘要卡片，复用既有队列与投递。

        仅合并被暂存过（next_retry_at 非空、已到期）的告警——这些必然是非
        critical（critical 入队时 next_retry_at 为空，立即单发）。数量不足合并
        阈值时保持原样，由派发主循环逐条投递。
        """
        if gov.digest_window_minutes <= 0:
            return

        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            due = repo.list_pending(channel="feishu", event_type="watchlist_alert", now=now, limit=200)
            candidates = [job for job in due if job.next_retry_at is not None]
            if len(candidates) < max(2, gov.digest_threshold):
                return

            items = [json.loads(job.payload_json) for job in candidates]
            dedupe_key = "alert-digest:" + ",".join(str(job.id) for job in candidates)
            repo.enqueue(
                channel="feishu",
                event_type="alert_digest",
                payload={"items": items},
                dedupe_key=dedupe_key,
            )
            for job in candidates:
                repo.mark_sent(job.id, sent_at=now, lease_token=None)
            # 摘要落库与源告警消费在同一事务内提交。
            session.commit()

    def _apply_quiet_hours(self, *, now: datetime, gov: GovernanceConfig) -> None:
        """免打扰时段内暂缓非 critical 的到期告警：顺延 next_retry_at 到时段结束。

        critical（极端情绪 / 重大异动）不受限制，继续走派发主循环立即投递。
        暂缓不计入失败重试次数，也不修改 attempt_count。
        """
        if not self._is_quiet_hours(now, gov):
            return

        quiet_end = self._next_quiet_hours_end(now, gov)
        with SessionLocal() as session:
            repo = NotificationJobRepository(session)
            for job in repo.list_pending(channel="feishu", now=now, limit=200):
                payload = json.loads(job.payload_json)
                if self._classify_severity(job.event_type, payload) == SEVERITY_CRITICAL:
                    continue
                repo.mark_retryable_failure(
                    job.id,
                    error="deferred:quiet_hours",
                    next_retry_at=quiet_end,
                    lease_token=None,
                )
            session.commit()

    @staticmethod
    def _parse_hhmm(value: str | None) -> tuple[int, int] | None:
        if not value:
            return None
        try:
            hour_str, minute_str = value.split(":", 1)
            hour, minute = int(hour_str), int(minute_str)
        except (ValueError, AttributeError):
            return None
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute
        return None

    @staticmethod
    def _resolve_zone(tz_name: str) -> ZoneInfo | timezone:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.warning("invalid quiet-hours timezone %s, falling back to UTC", tz_name)
            return UTC

    def _is_quiet_hours(self, now: datetime, gov: GovernanceConfig) -> bool:
        start = self._parse_hhmm(gov.quiet_hours_start)
        end = self._parse_hhmm(gov.quiet_hours_end)
        if start is None or end is None:
            return False

        local = now.astimezone(self._resolve_zone(gov.quiet_hours_tz))
        current_minutes = local.hour * 60 + local.minute
        start_minutes = start[0] * 60 + start[1]
        end_minutes = end[0] * 60 + end[1]
        if start_minutes == end_minutes:
            return False
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        # 跨夜区间（如 22:00-07:00）。
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _next_quiet_hours_end(self, now: datetime, gov: GovernanceConfig) -> datetime:
        end = self._parse_hhmm(gov.quiet_hours_end)
        zone = self._resolve_zone(gov.quiet_hours_tz)
        local = now.astimezone(zone)
        assert end is not None  # 仅在免打扰生效时调用
        end_local = local.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
        if end_local <= local:
            end_local = end_local + timedelta(days=1)
        return end_local.astimezone(UTC)

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
                session.commit()
            return

        sender = get_shared_feishu_sender(app_id=config.app_id, app_secret=config.decrypted_app_secret)
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
                session.commit()
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
                session.commit()
                if job.event_type == "watchlist_alert":
                    return
                return
            repo.mark_failed(job.id, error=error, lease_token=getattr(job, "lease_token", None))
            session.commit()
        if job.event_type == "watchlist_alert":
            self._release_watchlist_state(job)

    def _build_card_for_job(self, job: Any) -> dict[str, Any] | None:
        payload = json.loads(job.payload_json)
        if job.event_type == "news_batch":
            return build_news_batch_card(payload.get("items", []))
        if job.event_type == "alert_digest":
            return build_alert_digest_card(payload.get("items", []))
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
        if job.event_type == "digest":
            return build_digest_card(payload)
        if job.event_type == "sentiment_divergence":
            return build_sentiment_divergence_card(
                symbol=payload.get("symbol", ""),
                display_name=payload.get("display_name") or payload.get("symbol", ""),
                status=payload.get("status", ""),
                window_days=payload.get("window_days"),
                sentiment_avg=payload.get("sentiment_avg"),
                price_change_percent=payload.get("price_change_percent"),
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

    @staticmethod
    def _build_sentiment_divergence_dedupe_key(payload: dict[str, Any]) -> str:
        """symbol + 方向 + 当日（Asia/Shanghai）：同一天同方向重复命中不重复入队。

        `enqueue()` 对相同 dedupe_key 是幂等 upsert（见
        `NotificationJobRepository.enqueue`），所以 30 分钟一次的周期检查在同一天
        内反复命中同一 symbol/方向时，只有第一次真正建行，后续调用直接返回既有行，
        不会往外重复发送。
        """
        symbol = str(payload.get("symbol") or "").strip().upper()
        status_value = str(payload.get("status") or "").strip()
        detected_at_raw = payload.get("detected_at")
        detected_at: datetime | None = None
        if isinstance(detected_at_raw, datetime):
            detected_at = detected_at_raw
        elif isinstance(detected_at_raw, str) and detected_at_raw:
            try:
                detected_at = datetime.fromisoformat(detected_at_raw.replace("Z", "+00:00"))
            except ValueError:
                detected_at = None
        if detected_at is None:
            detected_at = _utc_now()
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=UTC)
        local_date = detected_at.astimezone(_SENTIMENT_DIVERGENCE_DEDUPE_TZ).date().isoformat()
        return f"sentiment-divergence:{symbol}:{status_value}:{local_date}"

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
