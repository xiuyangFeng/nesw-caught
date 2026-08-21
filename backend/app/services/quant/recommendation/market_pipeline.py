"""真实选票流水线：读独立行情库 + 主库规则新闻提及，三 sleeve 确定性打分。

与 pipeline.py 的合成流水线并列存在（互不修改）：run_market_pipeline 消费真实
数据，run_synthetic_pipeline 消费夹具，两者共用 contracts/candidate/factors 等
底层契约。LLM 不参与本文件任何判分逻辑。
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.models.market_data import DailyBar, FinancialFact, FundFlowDaily
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.services.a_share_search_service import get_all_a_shares
from app.services.quant.candidate import transition
from app.services.quant.contracts import (
    Board,
    Candidate,
    CandidateState,
    Horizon,
    PipelineResult,
    RunStatus,
    RunVersions,
    Sleeve,
    StageLog,
)
from app.services.quant.factors import score_event, score_fundamental, score_trend
from app.services.quant.recommendation.pipeline import compute_result_hash
from app.services.quant.trading_rules import is_limit_up_open
from app.services.quant.universe import DEFAULT_MIN_LIST_DAYS, DEFAULT_MIN_MEDIAN_AMOUNT_20D

# 规则新闻提及的观察窗口：近 7 个自然日，novelty 随天数线性衰减到 0。
EVENT_MENTION_WINDOW_DAYS = 7
# materiality 的命中次数分母：3 条及以上视为满分证据密度。
EVENT_MATERIALITY_DIVISOR = 3
# 规则命中新闻证据等级固定为 C（弱证据）：不给规则命中发 A/B，诚实优先。
EVENT_EVIDENCE_GRADE = "C"


def _stage(name: str, status: str, **detail: Any) -> StageLog:
    return StageLog(stage=name, status=status, detail=detail)


def _as_naive_utc(value: datetime) -> datetime:
    """SQLite 的 DateTime(timezone=True) 列不保真时区：写入 UTC-aware 值，读回是
    naive datetime（数值仍是 UTC）。这里统一剥离 tzinfo，保证与库内已存值可比较。
    """
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _infer_board(symbol: str) -> Board:
    """按代码前缀近似板块，用于涨跌停闸门取限价比例。

    688→科创板；300/301→创业板；北交所(.BJ 后缀且代码 8/4 开头)→北交所；
    其余按主板 10% 处理。北交所代码前缀存在 9 开头等未覆盖情形，属已知简化
    （见设计文档风险项），后续若要精确覆盖需要补充证券主数据的板块字段。
    """
    code, _, exchange = symbol.upper().partition(".")
    if code.startswith("688"):
        return Board.STAR
    if code.startswith(("300", "301")):
        return Board.CHINEXT
    if exchange == "BJ" and code.startswith(("8", "4")):
        return Board.BSE
    return Board.MAIN


def _walk_to_target(item: Candidate) -> None:
    """把候选从 DISCOVERED 经状态机迁移到目标终态（WATCH/QUALIFIED），全程带 reason_code。"""
    target = item.state
    state = transition(CandidateState.DISCOVERED, CandidateState.VALIDATING, "market_pipeline_discovered")
    item.state = transition(state, target, item.reason_code)


def _degraded_result(versions: RunVersions) -> PipelineResult:
    stage = _stage(
        "data_gate",
        "degraded",
        empty_reason="no_market_data",
        hint="执行 `make quant-backfill` 回填行情数据后再运行选票流水线。",
    )
    return PipelineResult(
        versions=versions,
        items=[],
        qualified=[],
        empty_reason="no_market_data",
        empty_reason_detail="行情库尚无日线数据，请先执行 `make quant-backfill` 回填后再运行选票流水线。",
        result_hash=compute_result_hash(versions, []),
        stages=[stage],
        status=RunStatus.DEGRADED,
    )


def _load_display_name_index() -> dict[str, str]:
    return {row["symbol"].upper(): row.get("display_name", "") for row in get_all_a_shares()}


def _build_universe(versions: RunVersions) -> tuple[
    list[str],
    dict[str, list[DailyBar]],
    dict[str, FundFlowDaily],
    date | None,
    bool,
]:
    """从行情库派生当日可交易池 U2，返回 (universe, 20日窗口, 最新资金流, last_trade_date, stale)。"""
    with MarketSessionLocal() as market_session:
        last_trade_date = market_session.scalar(select(func.max(DailyBar.trade_date)))
        if last_trade_date is None:
            return [], {}, {}, None, False

        bar_counts = dict(
            market_session.execute(select(DailyBar.symbol, func.count()).group_by(DailyBar.symbol)).all()
        )
        latest_bar_symbols = set(
            market_session.scalars(select(DailyBar.symbol).where(DailyBar.trade_date == last_trade_date))
        )
        listed_enough = sorted(
            symbol
            for symbol, count in bar_counts.items()
            if count >= DEFAULT_MIN_LIST_DAYS and symbol in latest_bar_symbols
        )

        universe: list[str] = []
        window_by_symbol: dict[str, list[DailyBar]] = {}
        for symbol in listed_enough:
            window = list(
                market_session.scalars(
                    select(DailyBar)
                    .where(DailyBar.symbol == symbol)
                    .order_by(DailyBar.trade_date.desc())
                    .limit(20)
                )
            )
            if not window:
                continue
            median_amount = statistics.median(bar.amount for bar in window)
            if median_amount < DEFAULT_MIN_MEDIAN_AMOUNT_20D:
                continue
            universe.append(symbol)
            window_by_symbol[symbol] = window

        flow_by_symbol: dict[str, FundFlowDaily] = {}
        if universe:
            flow_rows = market_session.scalars(
                select(FundFlowDaily)
                .where(FundFlowDaily.symbol.in_(universe))
                .order_by(FundFlowDaily.symbol, FundFlowDaily.trade_date.desc())
            )
            for row in flow_rows:
                # 已按 symbol, trade_date desc 排序，每个 symbol 首次出现即最新一条。
                flow_by_symbol.setdefault(row.symbol, row)

    stale = (versions.source_cutoff.date() - last_trade_date).days > 5
    return universe, window_by_symbol, flow_by_symbol, last_trade_date, stale


def _load_mentions(universe: list[str], versions: RunVersions) -> dict[str, list[tuple[int, datetime]]]:
    """近 7 日规则命中新闻提及，只在 U2 范围内聚合（事件证据必须落在可交易池才产候选）。"""
    if not universe:
        return {}
    window_start = _as_naive_utc(versions.source_cutoff - timedelta(days=EVENT_MENTION_WINDOW_DAYS))
    cutoff = _as_naive_utc(versions.source_cutoff)
    mentions_by_symbol: dict[str, list[tuple[int, datetime]]] = {}
    with SessionLocal() as session:
        rows = session.execute(
            select(NewsStockMention.symbol, NewsStockMention.news_id, NewsItem.effective_at)
            .join(NewsItem, NewsItem.id == NewsStockMention.news_id)
            .where(
                NewsStockMention.mention_type == "rule",
                NewsStockMention.symbol.in_(universe),
                NewsItem.effective_at >= window_start,
                NewsItem.effective_at <= cutoff,
            )
        ).all()
    for symbol, news_id, effective_at in rows:
        mentions_by_symbol.setdefault(symbol, []).append((news_id, effective_at))
    return mentions_by_symbol


def _apply_limit_up_gate(symbol: str, window: list[DailyBar] | None) -> str | None:
    """qualified 候选若最新开盘即触涨跌停，判定不可成交，返回降级 reason_code；否则 None。"""
    if not window or len(window) < 2:
        return None
    latest_bar, prev_bar = window[0], window[1]
    board = _infer_board(symbol)
    if is_limit_up_open(latest_bar.open, prev_bar.close, board):
        return "limit_up_open_unfillable"
    return None


def _build_trend_candidates(
    universe: list[str],
    window_by_symbol: dict[str, list[DailyBar]],
    flow_by_symbol: dict[str, FundFlowDaily],
    name_index: dict[str, str],
    versions: RunVersions,
) -> list[Candidate]:
    items: list[Candidate] = []
    for symbol in universe:
        window = window_by_symbol[symbol]
        latest_bar = window[0]
        adv = statistics.fmean(bar.amount for bar in window)
        flow_row = flow_by_symbol.get(symbol)
        inflow = flow_row.main_net_inflow if flow_row is not None else None
        score = score_trend(inflow=inflow, adv=adv)

        oldest_bar = window[-1]
        ret_20d = (latest_bar.close - oldest_bar.close) / oldest_bar.close if oldest_bar.close else 0.0
        breakdown = dict(score.breakdown)
        breakdown["ret_20d"] = round(ret_20d, 6)

        target_state = CandidateState.QUALIFIED if score.qualify else CandidateState.WATCH
        reason_code = score.reason_code
        if target_state is CandidateState.QUALIFIED:
            gate_reason = _apply_limit_up_gate(symbol, window)
            if gate_reason is not None:
                target_state = CandidateState.WATCH
                reason_code = gate_reason

        candidate = Candidate(
            symbol=symbol,
            display_name=name_index.get(symbol, symbol),
            sleeve=Sleeve.TREND_FLOW,
            horizon=Horizon.D20,
            state=target_state,
            reason_code=reason_code,
            deterministic_score=round(score.score, 6),
            factor_breakdown=breakdown,
            evidence_ids=[f"market-bar-{symbol}-{latest_bar.trade_date.isoformat()}"],
            thesis_md=(
                f"主力净流入 {inflow:,.0f} 元，20 日均成交额 {adv:,.0f} 元。"
                if inflow is not None
                else "缺少最新资金流数据，趋势分按 0 流入计算。"
            ),
            invalidation_condition="主力资金转为净流出或 20 日流动性跌破门槛",
            valid_until=versions.source_cutoff.date() + timedelta(days=20),
        )
        _walk_to_target(candidate)
        items.append(candidate)
    return items


def _build_event_candidates(
    universe: list[str],
    mentions_by_symbol: dict[str, list[tuple[int, datetime]]],
    window_by_symbol: dict[str, list[DailyBar]],
    name_index: dict[str, str],
    versions: RunVersions,
) -> list[Candidate]:
    items: list[Candidate] = []
    cutoff_date = _as_naive_utc(versions.source_cutoff).date()
    for symbol in universe:
        mentions = mentions_by_symbol.get(symbol)
        if not mentions:
            continue  # 无 mention 不产生候选：诚实优先，不编造事件证据。

        news_ids = sorted({news_id for news_id, _ in mentions})
        latest_dt = max(effective_at for _, effective_at in mentions)
        days_since = max(0, (cutoff_date - latest_dt.date()).days)
        novelty = max(0.0, min(1.0, 1 - days_since / EVENT_MENTION_WINDOW_DAYS))
        materiality = min(1.0, len(mentions) / EVENT_MATERIALITY_DIVISOR)
        score = score_event(novelty=novelty, materiality=materiality, grade=EVENT_EVIDENCE_GRADE)

        target_state = CandidateState.QUALIFIED if score.qualify else CandidateState.WATCH
        reason_code = score.reason_code
        if target_state is CandidateState.QUALIFIED:
            gate_reason = _apply_limit_up_gate(symbol, window_by_symbol.get(symbol))
            if gate_reason is not None:
                target_state = CandidateState.WATCH
                reason_code = gate_reason

        candidate = Candidate(
            symbol=symbol,
            display_name=name_index.get(symbol, symbol),
            sleeve=Sleeve.EVENT_CATALYST,
            horizon=Horizon.D5,
            state=target_state,
            reason_code=reason_code,
            deterministic_score=round(score.score, 6),
            factor_breakdown=dict(score.breakdown),
            evidence_ids=[f"news-{news_id}" for news_id in news_ids],
            thesis_md=(
                f"近 7 日 {len(mentions)} 条规则命中新闻提及，最近一条 {latest_dt.date().isoformat()}；"
                "规则命中证据等级 C（弱证据），仅进入观察池，不发 A/B。"
            ),
            invalidation_condition="7 日窗口内新闻热度衰减且无后续验证",
            valid_until=versions.source_cutoff.date() + timedelta(days=EVENT_MENTION_WINDOW_DAYS),
        )
        _walk_to_target(candidate)
        items.append(candidate)
    return items


def _load_latest_financials(
    universe: list[str],
    cutoff_date: date,
) -> tuple[dict[str, dict[date, dict[str, float | None]]], dict[str, date]]:
    """读 financial_fact（PIT：仅 available_at <= 截点），返回 (by_symbol, latest_period)。"""
    if not universe:
        return {}, {}
    with MarketSessionLocal() as market_session:
        rows = list(
            market_session.scalars(
                select(FinancialFact)
                .where(FinancialFact.symbol.in_(universe))
                .order_by(FinancialFact.symbol, FinancialFact.period_end.desc())
            )
        )
    by_symbol: dict[str, dict[date, dict[str, float | None]]] = {}
    for row in rows:
        if row.available_at is not None and row.available_at > cutoff_date:
            continue  # 披露日晚于截点：不可用于该截点决策
        period_metrics = by_symbol.setdefault(row.symbol, {}).setdefault(row.period_end, {})
        period_metrics[row.metric_key] = row.value
        if row.available_at is not None:
            period_metrics["_available_at"] = row.available_at.isoformat()
    latest_period: dict[str, date] = {symbol: max(periods) for symbol, periods in by_symbol.items() if periods}
    return by_symbol, latest_period


def _build_fundamental_candidates(
    universe: list[str],
    name_index: dict[str, str],
    versions: RunVersions,
) -> tuple[list[Candidate], list[str], list[str]]:
    """基本面重估：有财务覆盖的标的按单季净利/营收同比 + ROE 给分，只产 WATCH（不晋级）。

    指标来自东财主要财务指标报告（DJD_*_YOY 单季同比、ROEJQ 加权 ROE），
    均为百分数转比值，无需跨期查找。
    """
    cutoff_date = _as_naive_utc(versions.source_cutoff).date()
    by_symbol, latest_period = _load_latest_financials(universe, cutoff_date)
    items: list[Candidate] = []
    covered: list[str] = []
    for symbol in universe:
        period_end = latest_period.get(symbol)
        if period_end is None:
            continue
        covered.append(symbol)
        metrics = by_symbol[symbol][period_end]
        score = score_fundamental(
            net_profit_yoy=metrics.get("net_profit_yoy"),
            revenue_yoy=metrics.get("revenue_yoy"),
            roe=metrics.get("roe"),
            covered=True,
        )
        thesis = (
            f"最新财报期 {period_end.isoformat()}（披露 {metrics.get('_available_at') or '见详情'}）："
            f"单季净利同比 {_fmt_pct(metrics.get('net_profit_yoy'))}，"
            f"单季营收同比 {_fmt_pct(metrics.get('revenue_yoy'))}，ROE {metrics.get('roe') if metrics.get('roe') is not None else '—'}%。"
            "基本面 sleeve 只进观察池，暂不晋级。"
        )
        candidate = Candidate(
            symbol=symbol,
            display_name=name_index.get(symbol, symbol),
            sleeve=Sleeve.FUNDAMENTAL_REVALUE,
            horizon=Horizon.D60,
            state=CandidateState.WATCH,
            reason_code=score.reason_code,
            deterministic_score=round(score.score, 6),
            factor_breakdown=dict(score.breakdown),
            evidence_ids=[f"financial-{symbol}-{period_end.isoformat()}"],
            thesis_md=thesis,
            invalidation_condition="财报期更新或同比转负",
            valid_until=versions.source_cutoff.date() + timedelta(days=60),
        )
        _walk_to_target(candidate)
        items.append(candidate)

    gap_symbols = [symbol for symbol in universe if symbol not in set(covered)]
    return items, covered, gap_symbols


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def run_market_pipeline(*, versions: RunVersions) -> PipelineResult:
    """真实选票流水线主入口：data_gate → universe_u2 → 三 sleeve 打分 → 涨跌停闸门 → 排名/哈希。"""
    universe, window_by_symbol, flow_by_symbol, last_trade_date, stale = _build_universe(versions)
    if last_trade_date is None:
        return _degraded_result(versions)

    mentions_by_symbol = _load_mentions(universe, versions)
    name_index = _load_display_name_index()

    trend_items = _build_trend_candidates(universe, window_by_symbol, flow_by_symbol, name_index, versions)
    event_items = _build_event_candidates(universe, mentions_by_symbol, window_by_symbol, name_index, versions)
    fundamental_items, fundamental_covered, fundamental_gap = _build_fundamental_candidates(
        universe, name_index, versions
    )
    all_items = trend_items + event_items + fundamental_items

    qualified = [item for item in all_items if item.state is CandidateState.QUALIFIED]
    qualified.sort(key=lambda item: (-item.deterministic_score, item.symbol))
    for rank, item in enumerate(qualified, start=1):
        item.rank = rank

    empty_reason: str | None = None
    empty_detail: str | None = None
    if not qualified:
        empty_reason = "no_positive_edge"
        empty_detail = "今日无正期望机会：真实行情/资金流/新闻证据未过资格线，现金为合法结果。"

    downgraded = [item.symbol for item in all_items if item.reason_code == "limit_up_open_unfillable"]

    stages = [
        _stage(
            "data_gate",
            "ok",
            last_trade_date=last_trade_date.isoformat(),
            stale=stale,
            warning="行情数据滞后超过 5 个自然日，仍继续运行" if stale else None,
        ),
        _stage(
            "universe_u2",
            "ok",
            size=len(universe),
            min_list_days=DEFAULT_MIN_LIST_DAYS,
            min_median_amount_20d=DEFAULT_MIN_MEDIAN_AMOUNT_20D,
            symbols=universe,
        ),
        _stage(
            "sleeve_trend_flow",
            "ok",
            scored=len(trend_items),
            qualified=sum(1 for item in trend_items if item.state is CandidateState.QUALIFIED),
            watch=sum(1 for item in trend_items if item.state is CandidateState.WATCH),
        ),
        _stage(
            "sleeve_event_catalyst",
            "ok",
            scored=len(event_items),
            qualified=sum(1 for item in event_items if item.state is CandidateState.QUALIFIED),
            watch=sum(1 for item in event_items if item.state is CandidateState.WATCH),
            mentioned_symbols=sorted(mentions_by_symbol.keys()),
        ),
        _stage(
            "sleeve_fundamental_revalue",
            "ok",
            scored=len(fundamental_items),
            covered=len(fundamental_covered),
            watch=sum(1 for item in fundamental_items if item.state is CandidateState.WATCH),
            qualified=0,
            gap_symbols=len(fundamental_gap),
            note="财务未覆盖的标的显式 gap，不编造聚合候选；基本面 sleeve 暂不晋级。",
        ),
        _stage("limit_up_gate", "ok", downgraded=downgraded),
        _stage("qualify", "ok", qualified_count=len(qualified), empty_reason=empty_reason),
    ]

    return PipelineResult(
        versions=versions,
        items=all_items,
        qualified=qualified,
        empty_reason=empty_reason,
        empty_reason_detail=empty_detail,
        result_hash=compute_result_hash(versions, all_items),
        stages=stages,
        status=RunStatus.OK,
    )
