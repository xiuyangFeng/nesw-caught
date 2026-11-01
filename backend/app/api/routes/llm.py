import asyncio
import json
import time
from datetime import UTC

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_repository import NewsRepository
from app.schemas.llm import (
    LLMChatRequest,
    LLMConfigUpsertRequest,
    LLMConfigView,
    LLMConnectionTestView,
    LLMStatsView,
    LLMTranslateRequest,
    LLMTranslateView,
)
from app.services.llm_providers import LLMProviderError, build_async_provider, build_provider

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
        input_price_per_1k=config.input_price_per_1k,
        output_price_per_1k=config.output_price_per_1k,
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
            input_price_per_1k=payload.input_price_per_1k,
            output_price_per_1k=payload.output_price_per_1k,
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


def _load_chat_context(
    session: Session,
    payload: LLMChatRequest,
) -> tuple[object, list[dict[str, str]]]:
    """同步读取聊天所需的 provider 配置与新闻上下文。

    这里聚合了 chat_with_llm 进入流式/非流式分支前的全部同步 DB 读，
    统一通过一次 anyio.to_thread.run_sync 线程跳转执行，避免直接在事件
    循环线程里做同步 SQLite 读——一旦撞上写锁（busy_timeout 最长 30s），
    会阻塞该线程上的所有 async 请求与 SSE。
    """
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

    return config, messages


@router.post("/chat")
async def chat_with_llm(
    payload: LLMChatRequest,
    request: Request,
    session: Session = Depends(get_db_session),
):
    config, messages = await anyio.to_thread.run_sync(_load_chat_context, session, payload)

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
                    elif event_type == "reasoning":
                        yield f"data: {json.dumps({'reasoning': data})}\n\n"
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


def _compute_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    input_price_per_1k: float | None,
    output_price_per_1k: float | None,
) -> float | None:
    """按每 1K tokens 单价换算花费（美元）。

    完全没有配置单价（输入/输出单价均为 None）时返回 None，由调用方标注
    “成本不可用”；只要配置了其中之一，缺失项按 0 计入。
    """
    if input_price_per_1k is None and output_price_per_1k is None:
        return None
    return (
        (prompt_tokens / 1000.0) * (input_price_per_1k or 0.0)
        + (completion_tokens / 1000.0) * (output_price_per_1k or 0.0)
    )


@router.get("/stats", response_model=LLMStatsView)
def get_llm_stats(session: Session = Depends(get_db_session)):
    from datetime import datetime, timedelta

    from app.models.llm_token_usage import LLMTokenUsage

    repository = LLMProviderConfigRepository(session)
    # 模型名 -> (输入单价, 输出单价)：优先采用配置了单价的记录。
    pricing: dict[str, tuple[float | None, float | None]] = {}
    for cfg in repository.list_all():
        prices = (cfg.input_price_per_1k, cfg.output_price_per_1k)
        if cfg.model_name not in pricing or prices != (None, None):
            pricing[cfg.model_name] = prices

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
        cost_usd = _compute_cost_usd(prompt_tokens, completion_tokens, input_price, output_price)
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
            "input_price_per_1k": input_price,
            "output_price_per_1k": output_price,
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
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    stmt_month = (
        select(
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
            func.sum(LLMTokenUsage.completion_tokens).label("completion"),
        )
        .where(LLMTokenUsage.created_at >= month_start)
        .group_by(LLMTokenUsage.model_name)
    )
    month_cost: float | None = None
    for row in session.execute(stmt_month):
        input_price, output_price = pricing.get(row.model_name, (None, None))
        cost_usd = _compute_cost_usd(int(row.prompt or 0), int(row.completion or 0), input_price, output_price)
        if cost_usd is not None:
            month_cost = (month_cost or 0.0) + cost_usd

    default_config = repository.get_default()
    monthly_budget = default_config.monthly_budget_usd if default_config else None
    budget_available = monthly_budget is not None
    over_budget = bool(
        budget_available and month_cost is not None and month_cost > monthly_budget
    )
    usage_ratio = (
        month_cost / monthly_budget
        if (budget_available and monthly_budget and month_cost is not None)
        else None
    )
    budget = {
        "month": now.strftime("%Y-%m"),
        "month_cost_usd": month_cost,
        "monthly_budget_usd": monthly_budget,
        "budget_available": budget_available,
        "over_budget": over_budget,
        "usage_ratio": usage_ratio,
    }

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
