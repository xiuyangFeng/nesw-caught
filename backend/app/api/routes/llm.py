import asyncio
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_repository import NewsRepository
from app.schemas.llm import (
    LLMConfigUpsertRequest,
    LLMConfigView,
    LLMConnectionTestView,
    LLMTranslateRequest,
    LLMTranslateView,
    LLMChatRequest,
)
from app.services.llm_providers import LLMProviderError, build_provider, build_async_provider

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


@router.post("/chat")
async def chat_with_llm(
    payload: LLMChatRequest,
    request: Request,
    session: Session = Depends(get_db_session),
):
    repository = LLMProviderConfigRepository(session)
    config = None
    if payload.config_id is not None:
        config = repository.get_by_id(payload.config_id)
    if config is None:
        config = repository.get_default()

    if config is None:
        raise HTTPException(status_code=400, detail="LLM provider is not configured")

    # 构造消息上下文
    messages = []
    
    # 角色设定与新闻上下文
    system_prompt = "你是一个资深的金融投资与分析助手，能给出深刻的新闻解读和分析。"
    if payload.news_id is not None:
        news_repo = NewsRepository(session)
        news = news_repo.get_by_id(payload.news_id)
        if news is not None:
            article = news_repo.get_article(payload.news_id)
            news_context = f"系统提示：请结合以下关联新闻内容回答用户的问题。\n\n【新闻标题】：{news.title}\n"
            if news.source_name:
                news_context += f"【新闻来源】：{news.source_name}\n"
            if news.published_at:
                news_context += f"【发布时间】：{news.published_at.isoformat()}\n"
            if news.summary:
                news_context += f"【新闻摘要】：{news.summary}\n"
            if article and article.content_text:
                news_context += f"【新闻正文】：{article.content_text}\n"
            news_context += "\n请结合上述新闻内容，回答用户的相关提问。"
            system_prompt = news_context

    messages.append({"role": "system", "content": system_prompt})

    # 对话历史
    for msg in payload.history:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    # 当前用户提问
    messages.append({"role": "user", "content": payload.message})

    provider = build_async_provider(config)

    # 1. 流式返回
    if payload.stream:
        async def event_generator():
            try:
                async for event_type, data in provider.chat_stream(messages=messages):
                    if await request.is_disconnected():
                        break
                    if event_type == "failover":
                        yield f"data: {json.dumps({'failover': data})}\n\n"
                    else:
                        yield f"data: {json.dumps({'text': data})}\n\n"
            except asyncio.CancelledError:
                pass
            except LLMProviderError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': 'Internal error: ' + str(exc)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    
    # 2. 非流式返回（普通 JSON）
    else:
        try:
            # 拼接历史会话
            result = await provider.complete(messages=messages)
            res_payload = {"text": result.content}
            if result.failover is not None:
                res_payload["failover"] = result.failover
            return res_payload
        except LLMProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@router.get("/stats")
def get_llm_stats(session: Session = Depends(get_db_session)):
    from app.models.llm_token_usage import LLMTokenUsage
    
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
    for row in session.execute(stmt_model):
        model_stats.append({
            "model_name": row.model_name,
            "prompt_tokens": int(row.prompt or 0),
            "completion_tokens": int(row.completion or 0),
            "total_tokens": int(row.total or 0),
            "call_count": int(row.count or 0),
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
    }

    # Group by daily trend (last 7 days)
    from datetime import datetime, timedelta, timezone
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
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

