import time
from dataclasses import asdict
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.schemas.llm import (
    LLMConfigUpsertRequest,
    LLMConfigView,
    LLMConnectionTestView,
    LLMStatsView,
    LLMTranslateRequest,
    LLMTranslateView,
)
from app.services.llm_cost import budget_status, compute_cost_usd, load_pricing
from app.services.llm_providers import LLMProviderError, build_provider

router = APIRouter()
TRANSLATE_MAX_LENGTH = 4000


def _to_config_view(config, configured: bool = True) -> LLMConfigView:
    if config is None:
        return LLMConfigView(configured=False)

    plain_key = config.decrypted_api_key
    masked_key = None
    if plain_key:
        last_4 = plain_key[-4:] if len(plain_key) >= 4 else plain_key
        if plain_key.startswith("sk-"):
            masked_key = f"sk-***{last_4}"
        else:
            masked_key = f"***{last_4}"

    return LLMConfigView(
        configured=configured,
        id=config.id,
        provider_name=config.provider_name,
        display_name=config.display_name,
        model_name=config.model_name,
        base_url=config.base_url,
        api_key=masked_key,
        api_key_set=bool(config.api_key),
        is_active=config.is_active,
        is_default=config.is_default,
        input_price_per_1m=config.input_price_per_1m,
        output_price_per_1m=config.output_price_per_1m,
        monthly_budget_usd=config.monthly_budget_usd,
        updated_at=config.updated_at,
    )


@router.get("/config", response_model=LLMConfigView)
def get_llm_config(session: Session = Depends(get_db_session)) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_default()
    return _to_config_view(config)


@router.post("/config", response_model=LLMConfigView)
def upsert_llm_config(
    payload: LLMConfigUpsertRequest,
    session: Session = Depends(get_db_session),
) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config_id = None
    if "id" in payload.model_fields_set:
        config_id = payload.id
    else:
        active = repository.get_active()
        config_id = active.id if active is not None else None

    try:
        config = repository.upsert_config(
            config_id=config_id,
            provider_name=payload.provider_name.strip(),
            display_name=payload.display_name.strip() if payload.display_name else None,
            base_url=payload.base_url.strip() if payload.base_url else None,
            model_name=payload.model_name.strip(),
            api_key=payload.api_key.strip() if payload.api_key is not None else None,
            is_active=payload.is_active,
            is_default=payload.is_default,
            input_price_per_1m=payload.input_price_per_1m,
            output_price_per_1m=payload.output_price_per_1m,
            monthly_budget_usd=payload.monthly_budget_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_config_view(config)


@router.get("/config/all", response_model=list[LLMConfigView])
def get_all_llm_configs(session: Session = Depends(get_db_session)) -> list[LLMConfigView]:
    repository = LLMProviderConfigRepository(session)
    configs = repository.list_all()
    return [_to_config_view(c) for c in configs]


@router.delete("/config/{config_id}", status_code=204)
def delete_llm_config(config_id: int, session: Session = Depends(get_db_session)) -> None:
    repository = LLMProviderConfigRepository(session)
    success = repository.delete_by_id(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM config not found")


@router.post("/config/{config_id}/default", response_model=LLMConfigView)
def set_default_config(config_id: int, session: Session = Depends(get_db_session)) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config = repository.set_default(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM config not found")
    return _to_config_view(config)


@router.post("/config/{config_id}/active", response_model=LLMConfigView)
def toggle_active_config(
    config_id: int,
    is_active: bool,
    session: Session = Depends(get_db_session),
) -> LLMConfigView:
    repository = LLMProviderConfigRepository(session)
    config = repository.set_active_status(config_id, is_active)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM config not found")
    return _to_config_view(config)


@router.post("/translate", response_model=LLMTranslateView)
def translate_text(
    payload: LLMTranslateRequest,
    session: Session = Depends(get_db_session),
) -> LLMTranslateView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_default()
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


@router.post("/test", response_model=LLMConnectionTestView)
def test_llm_connection(session: Session = Depends(get_db_session)) -> LLMConnectionTestView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_default()
    if config is None:
        raise HTTPException(status_code=400, detail="llm provider is not configured")

    provider = build_provider(config)
    try:
        provider.test_connection()
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LLMConnectionTestView(
        provider_name=config.provider_name,
        model_name=config.model_name,
        message="LLM connection succeeded",
    )


@router.get("/stats", response_model=LLMStatsView)
def get_llm_stats(session: Session = Depends(get_db_session)):
    from datetime import datetime, timedelta

    from app.models.llm_token_usage import LLMTokenUsage

    pricing = load_pricing(session)

    # Group by model_name
    stmt_model = (
        select(
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
            func.sum(LLMTokenUsage.completion_tokens).label("completion"),
            func.sum(LLMTokenUsage.total_tokens).label("total"),
            func.count(LLMTokenUsage.id).label("count")
        )
        .group_by(LLMTokenUsage.model_name)
    )
    model_stats = []
    total_cost: float | None = None
    for row in session.execute(stmt_model):
        prompt_tokens = int(row.prompt or 0)
        completion_tokens = int(row.completion or 0)
        input_price, output_price = pricing.get(row.model_name, (None, None))
        cost_usd = compute_cost_usd(prompt_tokens, completion_tokens, input_price, output_price)
        if cost_usd is not None:
            total_cost = (total_cost or 0.0) + cost_usd
        model_stats.append({
            "model_name": row.model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": int(row.total or 0),
            "call_count": int(row.count or 0),
            "cost_usd": cost_usd,
            "cost_available": cost_usd is not None,
            "input_price_per_1m": input_price,
            "output_price_per_1m": output_price,
        })

    # Group by operation_type
    stmt_op = (
        select(
            LLMTokenUsage.operation_type,
            func.sum(LLMTokenUsage.total_tokens).label("total")
        )
        .group_by(LLMTokenUsage.operation_type)
    )
    op_stats = []
    for row in session.execute(stmt_op):
        op_stats.append({
            "operation_type": row.operation_type,
            "total_tokens": int(row.total or 0),
        })

    # Total overall stats
    stmt_total = select(
        func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
        func.sum(LLMTokenUsage.completion_tokens).label("completion"),
        func.sum(LLMTokenUsage.total_tokens).label("total")
    )
    total_row = session.execute(stmt_total).first()

    overall = {
        "prompt_tokens": int(total_row.prompt or 0) if total_row else 0,
        "completion_tokens": int(total_row.completion or 0) if total_row else 0,
        "total_tokens": int(total_row.total or 0) if total_row else 0,
        "cost_usd": total_cost,
        "cost_available": total_cost is not None,
    }

    # 本月累计花费 vs 月度预算（取默认模型配置上的 monthly_budget_usd）。
    now = datetime.now(UTC)
    budget = asdict(budget_status(session, now, pricing=pricing))

    # Group by daily trend (last 7 days)
    seven_days_ago = now - timedelta(days=7)
    stmt_daily = (
        select(
            func.date(LLMTokenUsage.created_at).label("day"),
            func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
            func.sum(LLMTokenUsage.completion_tokens).label("completion"),
            func.sum(LLMTokenUsage.total_tokens).label("total")
        )
        .where(LLMTokenUsage.created_at >= seven_days_ago)
        .group_by(func.date(LLMTokenUsage.created_at))
        .order_by(func.date(LLMTokenUsage.created_at).asc())
    )
    daily_stats = []
    for row in session.execute(stmt_daily):
        daily_stats.append({
            "date": str(row.day),
            "prompt_tokens": int(row.prompt or 0),
            "completion_tokens": int(row.completion or 0),
            "total_tokens": int(row.total or 0),
        })

    return {
        "overall": overall,
        "models": model_stats,
        "operations": op_stats,
        "daily": daily_stats,
        "budget": budget,
    }


@router.post("/config/{config_id}/ping", response_model=LLMConnectionTestView)
def ping_llm_config(
    config_id: int,
    session: Session = Depends(get_db_session)
) -> LLMConnectionTestView:
    repository = LLMProviderConfigRepository(session)
    config = repository.get_by_id(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="LLM config not found")

    provider = build_provider(config)
    start_time = time.perf_counter()
    try:
        provider.test_connection()
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    latency = (time.perf_counter() - start_time) * 1000.0
    return LLMConnectionTestView(
        provider_name=config.provider_name,
        model_name=config.model_name,
        message="LLM connection succeeded",
        latency_ms=round(latency, 2)
    )
