from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feishu_notify_config import FeishuNotifyConfig


class FeishuNotifyConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self) -> FeishuNotifyConfig | None:
        return self.session.scalar(
            select(FeishuNotifyConfig)
            .where(FeishuNotifyConfig.is_active.is_(True))
            .order_by(FeishuNotifyConfig.id.desc())
            .limit(1)
        )

    def get_first(self) -> FeishuNotifyConfig | None:
        return self.session.scalar(
            select(FeishuNotifyConfig).order_by(FeishuNotifyConfig.id.desc()).limit(1)
        )

    def upsert(
        self,
        app_id: str,
        app_secret: str | None,
        target_type: str,
        target_id: str,
        news_enabled: bool,
        news_keywords: str | None,
        news_batch_interval_minutes: int,
        alert_enabled: bool,
        analysis_enabled: bool,
        is_active: bool,
    ) -> FeishuNotifyConfig:
        existing = self.get_first()
        now = datetime.now(timezone.utc)

        from app.core.crypto import encrypt_key

        if existing is None:
            if not app_secret:
                raise ValueError("app_secret is required for initial configuration")
            config = FeishuNotifyConfig(
                app_id=app_id,
                app_secret=encrypt_key(app_secret),
                target_type=target_type,
                target_id=target_id,
                news_enabled=news_enabled,
                news_keywords=news_keywords,
                news_batch_interval_minutes=news_batch_interval_minutes,
                alert_enabled=alert_enabled,
                analysis_enabled=analysis_enabled,
                is_active=is_active,
                updated_at=now,
            )
            self.session.add(config)
            self.session.flush()
            self.session.refresh(config)
            return config

        existing.app_id = app_id
        if app_secret:
            existing.app_secret = encrypt_key(app_secret)
        existing.target_type = target_type
        existing.target_id = target_id
        existing.news_enabled = news_enabled
        existing.news_keywords = news_keywords
        existing.news_batch_interval_minutes = news_batch_interval_minutes
        existing.alert_enabled = alert_enabled
        existing.analysis_enabled = analysis_enabled
        existing.is_active = is_active
        existing.updated_at = now
        self.session.flush()
        self.session.refresh(existing)
        return existing
