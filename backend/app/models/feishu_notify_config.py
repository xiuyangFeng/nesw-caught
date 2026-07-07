from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeishuNotifyConfig(Base):
    __tablename__ = "feishu_notify_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[str] = mapped_column(String(128))
    app_secret: Mapped[str] = mapped_column(String(256))
    target_type: Mapped[str] = mapped_column(String(16), default="chat")
    target_id: Mapped[str] = mapped_column(String(128))
    news_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    news_keywords: Mapped[str | None] = mapped_column(Text(), default=None)
    news_batch_interval_minutes: Mapped[int] = mapped_column(Integer(), default=60)
    alert_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    analysis_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def decrypted_app_secret(self) -> str:
        from app.core.crypto import decrypt_key
        return decrypt_key(self.app_secret)
