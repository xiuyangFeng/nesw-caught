"""个股 AI 综合研判服务（本地语料 RAG，结构化研报）。

把某只股票近 N 天命中的所有新闻（标题 / 摘要 / 正文 ArticleContent）与最近价格
走势（PriceSnapshot）汇总，可选用 embedding 对新闻做相关性排序取 top-K，拼装
prompt 调用默认 LLM 产出结构化 JSON 研报（评级 / 催化剂 / 风险 / 关键时间线 /
摘要）。

设计要点：
- 复用既有能力：QuoteService（无网络的缓存行情 + 符号归一）、NewsMentionsRepository
  （命中新闻）、llm_providers（LLM 调用与 token 计量）、news_dedup 的 embedding
  余弦相似度做检索排序。
- 优雅降级：LLM 未配置或调用失败时，退回基于新闻情绪的规则要点汇总，字段结构不变，
  绝不抛出未捕获异常，绝不主动联网（get_cached_symbol_quote 仅读本地快照）。
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.schemas.stock_research import (
    StockResearchKeyEvent,
    StockResearchPriceContext,
    StockResearchRating,
    StockResearchReference,
    StockResearchReport,
)
from app.services.llm_providers import build_provider
from app.services.news_dedup import _cosine_similarity
from app.services.quote_service import QuoteService

logger = logging.getLogger(__name__)

# 参与研判的命中新闻上限（检索排序后取 top-K），控制 prompt 体量。
TOP_K_NEWS = 8
# 单条正文注入 prompt 的截断长度，避免 prompt 过大。
BODY_EXCERPT_CHARS = 500
SUMMARY_EXCERPT_CHARS = 300
# lookback_days 合法区间。
MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 30

_ALLOWED_RATINGS: set[str] = {
    "strong_bullish",
    "bullish",
    "neutral",
    "bearish",
    "strong_bearish",
    "unknown",
}

# LLM 可能返回的评级同义词，统一映射到枚举值。
_RATING_SYNONYMS: dict[str, StockResearchRating] = {
    "positive": "bullish",
    "buy": "bullish",
    "bull": "bullish",
    "overweight": "bullish",
    "看多": "bullish",
    "偏多": "bullish",
    "增持": "bullish",
    "strong_buy": "strong_bullish",
    "strong buy": "strong_bullish",
    "negative": "bearish",
    "sell": "bearish",
    "bear": "bearish",
    "underweight": "bearish",
    "看空": "bearish",
    "偏空": "bearish",
    "减持": "bearish",
    "strong_sell": "strong_bearish",
    "strong sell": "strong_bearish",
    "hold": "neutral",
    "neutral": "neutral",
    "中性": "neutral",
    "观望": "neutral",
}

_ALLOWED_IMPACTS = {"positive", "negative", "neutral"}


def synthesize_stock_research(
    symbol: str,
    session: Session,
    lookback_days: int = 7,
    *,
    quote_service: QuoteService | None = None,
) -> StockResearchReport:
    """生成某只股票的 AI 综合研判结构化研报。

    绝不抛出未捕获异常：任何 LLM/解析失败都会降级为规则要点汇总。
    """
    lookback_days = max(MIN_LOOKBACK_DAYS, min(MAX_LOOKBACK_DAYS, int(lookback_days)))
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)

    quote = (quote_service or QuoteService()).get_cached_symbol_quote(symbol, session)
    resolved_symbol = str(quote.get("symbol") or symbol.upper())
    market = str(quote.get("market") or "unknown")
    display_name = quote.get("display_name")

    recent_news = _collect_recent_news(session, resolved_symbol, cutoff)
    article_map = _article_map(session, [n.id for n in recent_news])
    price_context = _build_price_context(session, resolved_symbol, quote, cutoff)
    news_count = len(recent_news)

    config = LLMProviderConfigRepository(session).get_default()
    query_text = _relevance_query(resolved_symbol, display_name)

    if config is None:
        ranked = _rank_news(recent_news, provider=None, query_text=query_text)
        return _rule_based_report(
            resolved_symbol=resolved_symbol,
            market=market,
            display_name=display_name,
            lookback_days=lookback_days,
            generated_at=now,
            ranked_news=ranked,
            price_context=price_context,
            news_count=news_count,
            llm_error=None,
        )

    provider = build_provider(config)
    ranked = _rank_news(recent_news, provider=provider, query_text=query_text)

    if not ranked:
        # 没有可供综合的语料，直接给出规则降级（不浪费 LLM 调用）。
        return _rule_based_report(
            resolved_symbol=resolved_symbol,
            market=market,
            display_name=display_name,
            lookback_days=lookback_days,
            generated_at=now,
            ranked_news=ranked,
            price_context=price_context,
            news_count=news_count,
            llm_error=None,
        )

    try:
        result = provider.complete(
            messages=_build_messages(
                resolved_symbol=resolved_symbol,
                display_name=display_name,
                lookback_days=lookback_days,
                ranked_news=ranked,
                article_map=article_map,
                price_context=price_context,
            ),
            response_format={"type": "json_object"},
            operation_type="analysis",
        )
        payload = json.loads(result.content)
        if not isinstance(payload, dict):
            raise ValueError("llm research payload is not a json object")
        return _map_llm_payload(
            payload,
            resolved_symbol=resolved_symbol,
            market=market,
            display_name=display_name,
            lookback_days=lookback_days,
            generated_at=now,
            ranked_news=ranked,
            price_context=price_context,
            news_count=news_count,
            model_name=config.model_name,
            failover=result.failover,
        )
    except Exception as exc:  # noqa: BLE001 - 任何失败都降级，绝不上抛
        logger.warning("stock research synthesis fell back to rule mode for %s: %s", resolved_symbol, exc)
        return _rule_based_report(
            resolved_symbol=resolved_symbol,
            market=market,
            display_name=display_name,
            lookback_days=lookback_days,
            generated_at=now,
            ranked_news=ranked,
            price_context=price_context,
            news_count=news_count,
            llm_error=str(exc),
        )


def _collect_recent_news(session: Session, resolved_symbol: str, cutoff: datetime) -> list[NewsItem]:
    """取该 symbol 命中且在窗口内的新闻（已按发布时间倒序）。"""
    news_items = NewsMentionsRepository(session).list_related_news(resolved_symbol)
    recent: list[NewsItem] = []
    for news in news_items:
        published_at = _aware(news.published_at or news.fetched_at)
        if published_at >= cutoff:
            recent.append(news)
    return recent


def _article_map(session: Session, news_ids: list[int]) -> dict[int, str]:
    """批量取正文映射 news_id -> content_text（仅保留非空）。"""
    if not news_ids:
        return {}
    rows = session.scalars(
        select(ArticleContent).where(ArticleContent.news_id.in_(news_ids))
    ).all()
    return {row.news_id: row.content_text for row in rows if row.content_text}


def _build_price_context(
    session: Session,
    resolved_symbol: str,
    quote: dict,
    cutoff: datetime,
) -> StockResearchPriceContext:
    """汇总窗口内价格走势：最新价、最新涨跌幅、区间高低、区间累计涨跌幅。"""
    snapshots = list(
        session.scalars(
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol == resolved_symbol)
            .where(PriceSnapshot.fetched_at >= cutoff)
            .order_by(PriceSnapshot.fetched_at.asc())
        )
    )
    prices = [s.price for s in snapshots if s.price is not None]
    window_high = max(prices) if prices else None
    window_low = min(prices) if prices else None
    window_change_percent: float | None = None
    if len(prices) >= 2 and prices[0]:
        window_change_percent = round((prices[-1] - prices[0]) / prices[0] * 100, 4)

    return StockResearchPriceContext(
        price=quote.get("price"),
        change_percent=quote.get("change_percent"),
        window_high=window_high,
        window_low=window_low,
        window_change_percent=window_change_percent,
        snapshot_count=len(snapshots),
        status=quote.get("status"),
    )


def _relevance_query(resolved_symbol: str, display_name: str | None) -> str:
    name = display_name or resolved_symbol
    return f"{name} {resolved_symbol} 最新催化剂 业绩 政策 风险 股价走势"


def _rank_news(
    news_list: list[NewsItem],
    *,
    provider,
    query_text: str,
    top_k: int = TOP_K_NEWS,
) -> list[NewsItem]:
    """对命中新闻做相关性排序取 top-K。

    有可用 provider 且候选超过 top_k 时用 embedding 余弦相似度排序；否则（或
    embedding 失败）退回按新闻已有的发布时间倒序取前 top_k。embedding 失败绝不上抛。
    """
    if len(news_list) <= top_k or provider is None:
        return news_list[:top_k]
    try:
        query_vec = provider.embed_text(query_text)
        scored: list[tuple[float, NewsItem]] = []
        for news in news_list:
            text = f"{news.title} {news.summary or ''}".strip()
            similarity = _cosine_similarity(query_vec, provider.embed_text(text))
            scored.append((similarity, news))
        # 稳定排序：相似度相同者保留原有的时间倒序。
        scored.sort(key=lambda item: item[0], reverse=True)
        return [news for _, news in scored[:top_k]]
    except Exception as exc:  # noqa: BLE001 - embedding 失败退回时间序
        logger.warning("embedding relevance ranking failed, falling back to recency: %s", exc)
        return news_list[:top_k]


def _build_messages(
    *,
    resolved_symbol: str,
    display_name: str | None,
    lookback_days: int,
    ranked_news: list[NewsItem],
    article_map: dict[int, str],
    price_context: StockResearchPriceContext,
) -> list[dict[str, str]]:
    system_prompt = (
        "你是一名资深的港美股卖方分析师。请仅依据用户提供的本地新闻语料与价格走势，"
        "输出一份客观、结构化的个股综合研判。严格只返回一个 JSON 对象，不要任何多余文字，"
        "键固定为：\n"
        "- overall_rating：枚举之一 strong_bullish / bullish / neutral / bearish / strong_bearish；\n"
        "- rating_rationale：字符串，给出评级的核心理由；\n"
        "- summary：字符串，一段整体研判摘要；\n"
        "- bull_case：字符串数组，逐条列出利多催化剂；\n"
        "- bear_case：字符串数组，逐条列出风险与利空；\n"
        "- key_events：数组，元素为对象 {date, title, description, impact}，"
        "impact 取 positive / negative / neutral，按时间梳理关键事件。\n"
        "若语料不足以支撑结论，请如实在 summary 中说明并给出 neutral 评级。"
    )

    price_line = (
        f"最新价 {price_context.price}，最新涨跌幅 {price_context.change_percent}%，"
        f"窗口内高 {price_context.window_high} / 低 {price_context.window_low}，"
        f"窗口累计涨跌幅 {price_context.window_change_percent}%"
    )

    news_blocks: list[str] = []
    for idx, news in enumerate(ranked_news, 1):
        published_at = _aware(news.published_at or news.fetched_at)
        body = article_map.get(news.id)
        summary = (news.summary or "")[:SUMMARY_EXCERPT_CHARS]
        block = [
            f"[{idx}] 时间 {published_at.date().isoformat()} | 来源 {news.source_name} | 情绪 {news.sentiment_label or '未知'}",
            f"    标题：{news.title}",
        ]
        if summary:
            block.append(f"    摘要：{summary}")
        if body:
            block.append(f"    正文摘录：{body[:BODY_EXCERPT_CHARS]}")
        news_blocks.append("\n".join(block))

    user_prompt = (
        f"个股：{display_name or resolved_symbol}（{resolved_symbol}）\n"
        f"回溯窗口：近 {lookback_days} 天\n"
        f"价格走势：{price_line}\n\n"
        f"命中新闻语料（共 {len(ranked_news)} 条，已按相关性排序）：\n"
        + "\n\n".join(news_blocks)
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _map_llm_payload(
    payload: dict,
    *,
    resolved_symbol: str,
    market: str,
    display_name: str | None,
    lookback_days: int,
    generated_at: datetime,
    ranked_news: list[NewsItem],
    price_context: StockResearchPriceContext,
    news_count: int,
    model_name: str | None,
    failover: dict[str, str] | None,
) -> StockResearchReport:
    rating = _normalize_rating(payload.get("overall_rating"))
    summary = _clean_text(payload.get("summary")) or _fallback_summary(
        resolved_symbol, lookback_days, news_count
    )
    rationale = _clean_text(payload.get("rating_rationale")) or None
    bull_case = _string_list(payload.get("bull_case"))
    bear_case = _string_list(payload.get("bear_case"))
    key_events = _parse_key_events(payload.get("key_events"))
    if not key_events:
        key_events = _events_from_news(ranked_news)

    return StockResearchReport(
        symbol=resolved_symbol,
        market=market,
        display_name=display_name,
        generated_at=generated_at,
        lookback_days=lookback_days,
        mode="llm",
        overall_rating=rating,
        rating_rationale=rationale,
        summary=summary,
        bull_case=bull_case,
        bear_case=bear_case,
        key_events=key_events,
        price_context=price_context,
        references=_references(ranked_news),
        news_count=news_count,
        model_name=model_name,
        llm_error=None,
        failover=failover,
    )


def _rule_based_report(
    *,
    resolved_symbol: str,
    market: str,
    display_name: str | None,
    lookback_days: int,
    generated_at: datetime,
    ranked_news: list[NewsItem],
    price_context: StockResearchPriceContext,
    news_count: int,
    llm_error: str | None,
) -> StockResearchReport:
    """LLM 不可用/失败时的规则要点汇总。"""
    bull_case: list[str] = []
    bear_case: list[str] = []
    key_events: list[StockResearchKeyEvent] = []
    for news in ranked_news:
        label = (news.sentiment_label or "").lower()
        if label == "positive":
            impact = "positive"
            bull_case.append(news.title)
        elif label == "negative":
            impact = "negative"
            bear_case.append(news.title)
        else:
            impact = "neutral"
        published_at = _aware(news.published_at or news.fetched_at)
        key_events.append(
            StockResearchKeyEvent(
                date=published_at.date().isoformat(),
                title=news.title,
                description=(news.summary or None),
                impact=impact,
            )
        )

    rating = _rating_from_counts(len(bull_case), len(bear_case), news_count, price_context)
    summary = _rule_summary(
        resolved_symbol, display_name, lookback_days, news_count, len(bull_case), len(bear_case)
    )

    return StockResearchReport(
        symbol=resolved_symbol,
        market=market,
        display_name=display_name,
        generated_at=generated_at,
        lookback_days=lookback_days,
        mode="rule",
        overall_rating=rating,
        rating_rationale="LLM 未配置或调用失败，以下为基于新闻情绪的规则汇总。" if llm_error is not None or news_count else None,
        summary=summary,
        bull_case=bull_case,
        bear_case=bear_case,
        key_events=key_events,
        price_context=price_context,
        references=_references(ranked_news),
        news_count=news_count,
        model_name=None,
        llm_error=llm_error,
        failover=None,
    )


def _rating_from_counts(
    positives: int,
    negatives: int,
    news_count: int,
    price_context: StockResearchPriceContext,
) -> StockResearchRating:
    if news_count == 0:
        return "unknown"
    score = positives - negatives
    if score >= 3:
        return "strong_bullish"
    if score >= 1:
        return "bullish"
    if score <= -3:
        return "strong_bearish"
    if score <= -1:
        return "bearish"
    # 情绪打平时，用窗口价格方向做轻微倾斜。
    change = price_context.change_percent
    if change is not None:
        if change >= 3:
            return "bullish"
        if change <= -3:
            return "bearish"
    return "neutral"


def _events_from_news(ranked_news: list[NewsItem]) -> list[StockResearchKeyEvent]:
    events: list[StockResearchKeyEvent] = []
    for news in ranked_news:
        label = (news.sentiment_label or "").lower()
        impact = label if label in _ALLOWED_IMPACTS else "neutral"
        published_at = _aware(news.published_at or news.fetched_at)
        events.append(
            StockResearchKeyEvent(
                date=published_at.date().isoformat(),
                title=news.title,
                description=(news.summary or None),
                impact=impact,
            )
        )
    return events


def _references(ranked_news: list[NewsItem]) -> list[StockResearchReference]:
    return [
        StockResearchReference(
            news_id=news.id,
            title=news.title,
            source_name=news.source_name,
            canonical_url=news.canonical_url,
            published_at=news.published_at or news.fetched_at,
            sentiment_label=news.sentiment_label,
        )
        for news in ranked_news
    ]


def _normalize_rating(value: object) -> StockResearchRating:
    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_RATINGS:
        return raw  # type: ignore[return-value]
    return _RATING_SYNONYMS.get(raw, "neutral")


def _parse_key_events(value: object) -> list[StockResearchKeyEvent]:
    if not isinstance(value, list):
        return []
    events: list[StockResearchKeyEvent] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        if not title:
            continue
        impact_raw = str(item.get("impact") or "neutral").strip().lower()
        impact = impact_raw if impact_raw in _ALLOWED_IMPACTS else "neutral"
        date_raw = item.get("date")
        events.append(
            StockResearchKeyEvent(
                date=(str(date_raw).strip() or None) if date_raw is not None else None,
                title=title,
                description=_clean_text(item.get("description")) or None,
                impact=impact,  # type: ignore[arg-type]
            )
        )
    return events


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            cleaned.append(text)
    return cleaned


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _fallback_summary(resolved_symbol: str, lookback_days: int, news_count: int) -> str:
    return f"近 {lookback_days} 天 {resolved_symbol} 共命中 {news_count} 条相关新闻，已完成综合研判。"


def _rule_summary(
    resolved_symbol: str,
    display_name: str | None,
    lookback_days: int,
    news_count: int,
    positives: int,
    negatives: int,
) -> str:
    name = display_name or resolved_symbol
    if news_count == 0:
        return f"近 {lookback_days} 天未检索到 {name}（{resolved_symbol}）的关联新闻，暂无法生成综合研判。"
    return (
        f"近 {lookback_days} 天 {name}（{resolved_symbol}）共命中 {news_count} 条相关新闻，"
        f"其中偏多信号 {positives} 条、偏空信号 {negatives} 条（LLM 未启用，基于规则汇总）。"
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
