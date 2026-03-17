from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.llm_provider_config import LLMProviderConfig


class LLMProviderConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self) -> LLMProviderConfig | None:
        stmt = (
            select(LLMProviderConfig)
            .where(LLMProviderConfig.is_active.is_(True))
            .order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id.desc())
        )
        return self.session.scalar(stmt)

    def upsert_active(
        self,
        *,
        provider_name: str,
        display_name: str | None,
        base_url: str | None,
        model_name: str,
        api_key: str,
    ) -> LLMProviderConfig:
        existing = self.get_active()
        self.session.execute(update(LLMProviderConfig).values(is_active=False))

        if existing is None:
            existing = LLMProviderConfig(
                provider_name=provider_name,
                display_name=display_name,
                base_url=base_url,
                model_name=model_name,
                api_key=api_key,
                is_active=True,
            )
            self.session.add(existing)
        else:
            existing.provider_name = provider_name
            existing.display_name = display_name
            existing.base_url = base_url
            existing.model_name = model_name
            existing.api_key = api_key
            existing.is_active = True

        self.session.commit()
        self.session.refresh(existing)
        return existing
