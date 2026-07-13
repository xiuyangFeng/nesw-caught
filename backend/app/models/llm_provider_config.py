from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMProviderConfig(Base):
    __tablename__ = "llm_provider_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), default=None)
    base_url: Mapped[str | None] = mapped_column(Text(), default=None)
    model_name: Mapped[str] = mapped_column(String(128))
    api_key: Mapped[str] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean(), default=False, index=True)
    # 成本治理：每 1K tokens 的输入/输出单价（美元）与月度预算（美元），均可为空。
    input_price_per_1k: Mapped[float | None] = mapped_column(Float(), default=None)
    output_price_per_1k: Mapped[float | None] = mapped_column(Float(), default=None)
    monthly_budget_usd: Mapped[float | None] = mapped_column(Float(), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def decrypted_api_key(self) -> str:
        from app.core.crypto import decrypt_key
        return decrypt_key(self.api_key)

