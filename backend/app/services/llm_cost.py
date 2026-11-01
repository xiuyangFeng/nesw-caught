"""LLM 费用计算（单价单位：美元 / 百万 token）。

`/api/llm/stats` 与 AI 漏斗的预算闸共用这里的口径，避免两处各算一套。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.llm_token_usage import LLMTokenUsage
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository

TOKENS_PER_PRICE_UNIT = 1_000_000.0

Pricing = dict[str, tuple[float | None, float | None]]


def compute_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    input_price_per_1m: float | None,
    output_price_per_1m: float | None,
) -> float | None:
    """两个单价都没配置时返回 None（"成本不可用"）；只配其一时缺失项按 0 计。"""
    if input_price_per_1m is None and output_price_per_1m is None:
        return None
    return (prompt_tokens / TOKENS_PER_PRICE_UNIT) * (input_price_per_1m or 0.0) + (
        completion_tokens / TOKENS_PER_PRICE_UNIT
    ) * (output_price_per_1m or 0.0)


def load_pricing(session: Session) -> Pricing:
    """模型名 -> (输入单价, 输出单价)，同名多条时优先取配置了单价的记录。"""
    pricing: Pricing = {}
    for cfg in LLMProviderConfigRepository(session).list_all():
        prices = (cfg.input_price_per_1m, cfg.output_price_per_1m)
        if cfg.model_name not in pricing or prices != (None, None):
            pricing[cfg.model_name] = prices
    return pricing


def cost_since(session: Session, since: datetime, *, pricing: Pricing | None = None) -> float | None:
    """`since` 之后所有调用的费用合计；没有任何可计价的模型时返回 None。"""
    pricing = pricing if pricing is not None else load_pricing(session)
    stmt = (
        select(
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
            func.sum(LLMTokenUsage.completion_tokens).label("completion"),
        )
        .where(LLMTokenUsage.created_at >= since)
        .group_by(LLMTokenUsage.model_name)
    )
    total: float | None = None
    for row in session.execute(stmt):
        input_price, output_price = pricing.get(row.model_name, (None, None))
        cost = compute_cost_usd(int(row.prompt or 0), int(row.completion or 0), input_price, output_price)
        if cost is not None:
            total = (total or 0.0) + cost
    return total


@dataclass(frozen=True)
class BudgetStatus:
    month: str
    month_cost_usd: float | None
    monthly_budget_usd: float | None
    budget_available: bool
    over_budget: bool
    usage_ratio: float | None


def month_start(now: datetime) -> datetime:
    now = now.astimezone(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def budget_status(session: Session, now: datetime | None = None, *, pricing: Pricing | None = None) -> BudgetStatus:
    """本月累计花费 vs 默认模型配置上的月度预算。"""
    now = now or datetime.now(UTC)
    month_cost = cost_since(session, month_start(now), pricing=pricing)
    default_config = LLMProviderConfigRepository(session).get_default()
    monthly_budget = default_config.monthly_budget_usd if default_config else None
    budget_available = monthly_budget is not None
    over_budget = bool(budget_available and month_cost is not None and month_cost >= monthly_budget)
    usage_ratio = (
        month_cost / monthly_budget if (budget_available and monthly_budget and month_cost is not None) else None
    )
    return BudgetStatus(
        month=now.astimezone(UTC).strftime("%Y-%m"),
        month_cost_usd=month_cost,
        monthly_budget_usd=monthly_budget,
        budget_available=budget_available,
        over_budget=over_budget,
        usage_ratio=usage_ratio,
    )
