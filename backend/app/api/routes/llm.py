from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.schemas.llm import LLMConfigUpsertRequest, LLMConfigView, LLMTranslateRequest, LLMTranslateView
from app.services.llm_providers import LLMProviderError, build_provider

router = APIRouter()
TRANSLATE_MAX_LENGTH = 4000


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
    try:
        config = repository.upsert_active(
            provider_name=payload.provider_name.strip(),
            display_name=payload.display_name.strip() if payload.display_name else None,
            base_url=payload.base_url.strip() if payload.base_url else None,
            model_name=payload.model_name.strip(),
            api_key=payload.api_key.strip() if payload.api_key is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LLMConfigView(
        configured=True,
        provider_name=config.provider_name,
        display_name=config.display_name,
        model_name=config.model_name,
        base_url=config.base_url,
        api_key_set=bool(config.api_key),
        updated_at=config.updated_at,
    )


@router.post("/translate", response_model=LLMTranslateView)
def translate_text(
    payload: LLMTranslateRequest,
    session: Session = Depends(get_db_session),
) -> LLMTranslateView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_active()
    if config is None:
        raise HTTPException(status_code=400, detail="llm provider is not configured")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > TRANSLATE_MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"text exceeds max length {TRANSLATE_MAX_LENGTH}")

    provider = build_provider(config)
    try:
        translated_text = provider.generate_text(
            system_prompt=(
                "You translate social media posts into natural Chinese. "
                "Preserve tickers, proper nouns, emojis, tone, and line breaks. "
                "Do not add explanations or extra commentary."
            ),
            user_prompt=text,
        ).strip()
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not translated_text:
        raise HTTPException(status_code=502, detail="llm provider returned empty translation")

    return LLMTranslateView(
        provider_name=config.provider_name,
        model_name=config.model_name,
        translated_text=translated_text,
    )
