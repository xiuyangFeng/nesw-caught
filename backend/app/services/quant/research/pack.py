"""§6.1 纵横研究包：结构化事实 + 显式缺口，不编造目标价。"""

from __future__ import annotations

from dataclasses import dataclass, field

RESEARCH_MODULE_KEYS = (
    "business_model",
    "vertical",
    "horizontal",
    "chain",
    "valuation",
    "catalysts",
    "risk_reward",
    "latest_events",
)

DEFAULT_PEERS: dict[str, list[str]] = {
    "600519.SH": ["000858.SZ", "000568.SZ"],
    "000858.SZ": ["600519.SH", "000568.SZ"],
    "300750.SZ": ["002594.SZ", "300014.SZ"],
}


@dataclass
class ResearchModule:
    key: str
    question: str
    answer: str
    evidence_ids: list[str] = field(default_factory=list)
    gap: str | None = None


@dataclass
class ResearchPack:
    symbol: str
    display_name: str
    modules: list[ResearchModule]
    ask_ai_context: str


_QUESTIONS = {
    "business_model": "产品/客户/地区如何贡献收入与利润，真正的利润池在哪里",
    "vertical": "3～5 年收入、利润、毛利率、现金流、资本开支、应收、存货如何变化",
    "horizontal": "同板块、上下游、海外映射和替代路线谁更强",
    "chain": "上游价格、客户资本开支或政策如何传到本公司利润",
    "valuation": "当前价格隐含什么增长；悲观/基准/乐观情景需要哪些假设",
    "catalysts": "未来 3～12 个月什么会验证；什么出现即说明逻辑错",
    "risk_reward": "上行来自哪里、下行可能多大、流动性和拥挤度如何",
    "latest_events": "最近新闻与公告（研究包中的最新事件子模块）",
}


def peers_for(symbol: str) -> list[str]:
    return list(DEFAULT_PEERS.get(symbol.upper(), []))


def latest_financials(symbol: str) -> dict | None:
    """返回该标的最新财报期指标（当前视角，PIT 由 available_at 记录），无覆盖返回 None。"""
    from datetime import date

    from sqlalchemy import select

    from app.db.market_session import MarketSessionLocal
    from app.models.market_data import FinancialFact

    with MarketSessionLocal() as market_session:
        rows = list(
            market_session.scalars(
                select(FinancialFact).where(FinancialFact.symbol == symbol.upper())
            )
        )
    if not rows:
        return None
    by_period: dict[date, dict] = {}
    for row in rows:
        period = by_period.setdefault(row.period_end, {})
        period[row.metric_key] = row.value
        if row.available_at is not None:
            period["_available_at"] = row.available_at
    latest = max(by_period)
    metrics = by_period[latest]
    available = metrics.get("_available_at")
    return {
        "period_end": latest.isoformat(),
        "available_at": available.isoformat() if available is not None else None,
        "net_profit_yoy": metrics.get("net_profit_yoy"),
        "revenue_yoy": metrics.get("revenue_yoy"),
        "roe": metrics.get("roe"),
        "gross_margin": metrics.get("gross_margin"),
    }


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f} 亿元"
    return f"{value:,.0f} 元"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def build_research_pack(
    *,
    symbol: str,
    display_name: str = "",
    news: list[dict] | None = None,
    peers: list[str] | None = None,
    financials: dict | None = None,
) -> ResearchPack:
    symbol = symbol.upper()
    news = news or []
    peer_symbols = peers if peers is not None else peers_for(symbol)
    event_ids = [f"news:{item['id']}" for item in news if item.get("id") is not None]
    event_titles = "；".join(str(item.get("title") or "") for item in news[:5]) or "暂无命中新闻"

    if financials is not None:
        valuation_answer = (
            f"最新财报期 {financials.get('period_end', '—')}（披露 {financials.get('available_at') or '未记录'}）："
            f"单季净利同比 {_fmt_pct(financials.get('net_profit_yoy'))}、"
            f"单季营收同比 {_fmt_pct(financials.get('revenue_yoy'))}，"
            f"ROE {financials.get('roe') if financials.get('roe') is not None else '—'}%，"
            f"毛利率 {financials.get('gross_margin') if financials.get('gross_margin') is not None else '—'}%。"
            "基本面 sleeve 只进观察池；无一致预期数据，仍不给出目标价。"
        )
        valuation_gap = None
        financial_evidence = [f"financial:{symbol}:{financials.get('period_end', '')}"]
    else:
        valuation_answer = "无一致预期与规范财务字段时只展示假设缺口，不给出无依据价格锚或买卖点。"
        valuation_gap = "no_financials_or_consensus"
        financial_evidence = []

    modules = [
        ResearchModule(
            key="business_model",
            question=_QUESTIONS["business_model"],
            answer=f"{display_name or symbol} 的分部收入尚未接入官方财务事实表，不能把新闻叙事当成利润结构。",
            gap="no_financial_segments",
        ),
        ResearchModule(
            key="vertical",
            question=_QUESTIONS["vertical"],
            answer="缺少 3～5 年 point-in-time 财务序列，纵轴只保留事件节点，不回填虚假财报数字。",
            gap="no_financial_history",
        ),
        ResearchModule(
            key="horizontal",
            question=_QUESTIONS["horizontal"],
            answer=f"默认同业对照：{', '.join(peer_symbols) or '未配置'}。估值差待财务接入后计算。",
            evidence_ids=[f"peer:{item}" for item in peer_symbols],
            gap=None if peer_symbols else "no_peer_map",
        ),
        ResearchModule(
            key="chain",
            question=_QUESTIONS["chain"],
            answer="产业链边默认置信度低，高影响边需 A/B 级来源或人工确认。",
            gap="low_confidence_chain",
        ),
        ResearchModule(
            key="valuation",
            question=_QUESTIONS["valuation"],
            answer=valuation_answer,
            evidence_ids=financial_evidence,
            gap=valuation_gap,
        ),
        ResearchModule(
            key="catalysts",
            question=_QUESTIONS["catalysts"],
            answer="催化来自已分级事件；D 级传闻只触发检索，不能单独作为验证条件。",
            evidence_ids=event_ids,
        ),
        ResearchModule(
            key="risk_reward",
            question=_QUESTIONS["risk_reward"],
            answer="在概率校准完成前不把确定性分显示为胜率；下行用研究反证描述，不用伪装盘中止损价。",
            gap="score_uncalibrated",
        ),
        ResearchModule(
            key="latest_events",
            question=_QUESTIONS["latest_events"],
            answer=event_titles,
            evidence_ids=event_ids,
        ),
    ]
    context_lines = [
        f"DeskContext research_pack symbol={symbol} name={display_name}",
        "仅作研究材料。禁止修改排名、分数或仓位。数值必须引用 evidence_id。",
    ]
    for module in modules:
        context_lines.append(f"[{module.key}] Q:{module.question} A:{module.answer} gap={module.gap} ev={module.evidence_ids}")
    return ResearchPack(
        symbol=symbol,
        display_name=display_name,
        modules=modules,
        ask_ai_context="\n".join(context_lines),
    )
