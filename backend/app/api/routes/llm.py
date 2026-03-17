from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.schemas.llm import LLMConfigUpsertRequest, LLMConfigView

router = APIRouter()


@router.get("/config", response_model=LLMConfigView)
def get_llm_config(session: Session = Depends(get_db_session)) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_active()
    if config is None:
        return LLMConfigView(configured=False)

    return LLMConfigView(
        configured=True,
        provider_name=config.provider_name,
        display_name=config.display_name,
        model_name=config.model_name,
        base_url=config.base_url,
        api_key_set=bool(config.api_key),
        updated_at=config.updated_at,
    )


@router.post("/config", response_model=LLMConfigView)
def upsert_llm_config(
    payload: LLMConfigUpsertRequest,
    session: Session = Depends(get_db_session),
) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config = repository.upsert_active(
        provider_name=payload.provider_name.strip(),
        display_name=payload.display_name.strip() if payload.display_name else None,
        base_url=payload.base_url.strip() if payload.base_url else None,
        model_name=payload.model_name.strip(),
        api_key=payload.api_key.strip(),
    )
    return LLMConfigView(
        configured=True,
        provider_name=config.provider_name,
        display_name=config.display_name,
        model_name=config.model_name,
        base_url=config.base_url,
        api_key_set=bool(config.api_key),
        updated_at=config.updated_at,
    )
