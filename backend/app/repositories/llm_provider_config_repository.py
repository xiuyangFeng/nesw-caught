from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.models.llm_provider_config import LLMProviderConfig


def _normalize_base_url(provider_name: str, model_name: str, base_url: str | None) -> str | None:
    if base_url is None:
        return None

    normalized = base_url.strip()
    if (
        provider_name == "openai_compatible"
        and model_name.startswith("deepseek-")
        and normalized == "https://api.deepssek.com/v1"
    ):
        return "https://api.deepseek.com/v1"
    return normalized


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

    def get_default(self) -> LLMProviderConfig | None:
        stmt = (
            select(LLMProviderConfig)
            .where(LLMProviderConfig.is_default.is_(True))
            .order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id.desc())
        )
        config = self.session.scalar(stmt)
        if config is not None:
            return config
        return self.get_active()

    def get_by_id(self, config_id: int) -> LLMProviderConfig | None:
        stmt = select(LLMProviderConfig).where(LLMProviderConfig.id == config_id)
        return self.session.scalar(stmt)

    def list_all(self) -> list[LLMProviderConfig]:
        stmt = select(LLMProviderConfig).order_by(LLMProviderConfig.id.asc())
        return list(self.session.scalars(stmt))

    def delete_by_id(self, config_id: int) -> bool:
        config = self.get_by_id(config_id)
        if config is None:
            return False
        self.session.delete(config)
        self.session.commit()
        return True

    def set_default(self, config_id: int) -> LLMProviderConfig | None:
        config = self.get_by_id(config_id)
        if config is None:
            return None

        self.session.execute(update(LLMProviderConfig).values(is_default=False))
        config.is_default = True
        config.is_active = True
        self.session.commit()
        self.session.refresh(config)
        return config

    def set_active_status(self, config_id: int, is_active: bool) -> LLMProviderConfig | None:
        config = self.get_by_id(config_id)
        if config is None:
            return None

        config.is_active = is_active
        if not is_active and config.is_default:
            config.is_default = False

        self.session.commit()
        self.session.refresh(config)
        return config

    def upsert_config(
        self,
        *,
        config_id: int | None = None,
        provider_name: str,
        display_name: str | None = None,
        base_url: str | None = None,
        model_name: str,
        api_key: str | None = None,
        is_active: bool = True,
        is_default: bool = False,
    ) -> LLMProviderConfig:
        normalized_base_url = _normalize_base_url(provider_name, model_name, base_url)
        config = None
        if config_id is not None:
            config = self.get_by_id(config_id)

        from app.core.crypto import encrypt_key

        if api_key and (api_key.startswith("*") or "*" in api_key):
            effective_api_key = config.api_key if config is not None else None
        elif api_key:
            effective_api_key = encrypt_key(api_key)
        else:
            effective_api_key = config.api_key if config is not None else None

        if not effective_api_key:
            raise ValueError("api key is required when creating the first llm config")

        if config is None:
            stmt_count = select(func.count(LLMProviderConfig.id))
            total_configs = self.session.scalar(stmt_count) or 0
            if total_configs == 0:
                is_default = True
                is_active = True

            config = LLMProviderConfig(
                provider_name=provider_name,
                display_name=display_name,
                base_url=normalized_base_url,
                model_name=model_name,
                api_key=effective_api_key,
                is_active=is_active,
                is_default=is_default,
            )
            self.session.add(config)
        else:
            config.provider_name = provider_name
            config.display_name = display_name
            config.base_url = normalized_base_url
            config.model_name = model_name
            config.api_key = effective_api_key
            config.is_active = is_active
            config.is_default = is_default

        if is_default:
            self.session.flush()
            self.session.execute(
                update(LLMProviderConfig)
                .where(LLMProviderConfig.id != config.id)
                .values(is_default=False)
            )

        self.session.commit()
        self.session.refresh(config)
        return config

    def upsert_active(
        self,
        *,
        provider_name: str,
        display_name: str | None,
        base_url: str | None,
        model_name: str,
        api_key: str | None,
    ) -> LLMProviderConfig:
        active = self.get_active()
        config_id = active.id if active is not None else None
        return self.upsert_config(
            config_id=config_id,
            provider_name=provider_name,
            display_name=display_name,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            is_active=True,
            is_default=True,
        )
