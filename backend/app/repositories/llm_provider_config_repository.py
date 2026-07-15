from sqlalchemy import func, select, update
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

    def get_backup(self, exclude_id: int) -> LLMProviderConfig | None:
        stmt = (
            select(LLMProviderConfig)
            .where(LLMProviderConfig.is_active.is_(True))
            .where(LLMProviderConfig.id != exclude_id)
            .order_by(LLMProviderConfig.is_default.desc(), LLMProviderConfig.updated_at.desc())
        )
        return self.session.scalar(stmt)

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
        self.session.flush()
        return True

    def set_default(self, config_id: int) -> LLMProviderConfig | None:
        config = self.get_by_id(config_id)
        if config is None:
            return None

        self.session.execute(update(LLMProviderConfig).values(is_default=False))
        config.is_default = True
        config.is_active = True
        self.session.flush()
        self.session.refresh(config)
        return config

    def set_active_status(self, config_id: int, is_active: bool) -> LLMProviderConfig | None:
        config = self.get_by_id(config_id)
        if config is None:
            return None

        config.is_active = is_active
        if not is_active and config.is_default:
            config.is_default = False

        self.session.flush()
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
        input_price_per_1k: float | None = None,
        output_price_per_1k: float | None = None,
        monthly_budget_usd: float | None = None,
    ) -> LLMProviderConfig:
        normalized_base_url = _normalize_base_url(provider_name, model_name, base_url)
        config = None
        if config_id is not None:
            config = self.get_by_id(config_id)

        # 检查 base_url 是否修改了
        base_url_changed = False
        if config is not None and config.base_url != normalized_base_url:
            base_url_changed = True

        from app.core.crypto import encrypt_key

        api_key_is_masked_or_omitted = (not api_key) or (api_key.startswith("*") or "*" in api_key)
        if base_url_changed and api_key_is_masked_or_omitted:
            raise ValueError("修改 base_url 时必须重新输入明文 API Key，不能省略或使用掩码 Key，以防止 Key 被窃取")

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
                input_price_per_1k=input_price_per_1k,
                output_price_per_1k=output_price_per_1k,
                monthly_budget_usd=monthly_budget_usd,
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
            # 价格/预算为可选、非敏感字段：仅在显式传入时更新，避免不感知
            # 价格的调用方（如 upsert_active）把已配置的单价意外清空。
            if input_price_per_1k is not None:
                config.input_price_per_1k = input_price_per_1k
            if output_price_per_1k is not None:
                config.output_price_per_1k = output_price_per_1k
            if monthly_budget_usd is not None:
                config.monthly_budget_usd = monthly_budget_usd

        if is_default:
            self.session.flush()
            self.session.execute(
                update(LLMProviderConfig)
                .where(LLMProviderConfig.id != config.id)
                .values(is_default=False)
            )

        self.session.flush()
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
