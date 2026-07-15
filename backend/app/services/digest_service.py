"""每日盘前/盘后 AI 简报（Daily Digest）生成服务。

设计要点：
- ``generate_digest`` 收集近 N 小时新闻 + 自选股命中 + 情绪聚合，拼 prompt，
  调用默认 LLM provider 生成结构化 4 段简报；LLM 不可用/未配置/异常时优雅降级为
  基于规则的纯文本摘要，绝不向上抛未捕获异常。
- 维护一个进程内"最新 digest"单例（线程安全），并把最新一份写到
  ``<data>/latest_digest.json``（仿照 app_token 的本地文件做法，写失败只 log）。
- 不新增数据库表/迁移。
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.repositories.news_repository import NewsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.llm_providers import build_provider

logger = logging.getLogger(__name__)

# 简报固定包含的 4 个 section（顺序固定，标题为中文）。
SECTION_OVERNIGHT = "隔夜/当日重点"
SECTION_WATCHLIST = "自选股相关"
SECTION_SENTIMENT = "整体情绪方向"
SECTION_RISK = "风险提示"

# LLM 返回 JSON 的键与 section 的映射。
_LLM_KEYS = ("overnight", "watchlist", "sentiment", "risk")

_MARKET_LABELS = {"all": "全市场", "hk": "港股", "us": "美股", "cn": "A股"}

_SYSTEM_PROMPT = (
    "你是一名港美股盘前/盘后简报编辑，帮助不盯盘的个人投资者快速掌握重点。"
    "根据提供的新闻标题、自选股命中情况与情绪聚合数据，输出一份 JSON，"
    "键为 overnight（隔夜/当日重点）、watchlist（自选股相关）、"
    "sentiment（整体情绪方向）、risk（风险提示），每个值为一段简洁的中文纯文本，"
    "客观、不臆造未提供的数据，不给出投资建议。只返回 JSON。"
)


@dataclass(frozen=True)
class DigestSection:
    title: str
    body: str


@dataclass(frozen=True)
class Digest:
    title: str
    market_scope: str
    generated_at: datetime  # tz-aware UTC
    generated_by: str  # "llm" | "rule"
    model_name: str | None
    sections: list[DigestSection]

    def to_payload(self) -> dict[str, Any]:
        """序列化为可 JSON 化的 dict（用于本地快照文件与飞书推送 payload）。"""
        return {
            "title": self.title,
            "market_scope": self.market_scope,
            "generated_at": self.generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "generated_by": self.generated_by,
            "model_name": self.model_name,
            "sections": [{"title": s.title, "body": s.body} for s in self.sections],
        }


@dataclass
class _DigestContext:
    market_scope: str
    lookback_hours: int
    total_news: int
    recent_titles: list[str]
    watchlist_hits: list[str]
    sentiment_counts: dict[str, int]
    prompt: str


# --- 进程内"最新 digest"单例（线程安全）---------------------------------------

_latest_lock = threading.Lock()
_latest_digest: Digest | None = None


def get_latest_digest() -> Digest | None:
    with _latest_lock:
        return _latest_digest


def set_latest_digest(digest: Digest) -> None:
    global _latest_digest
    with _latest_lock:
        _latest_digest = digest


def reset_latest_digest() -> None:
    """仅供测试重置单例。"""
    global _latest_digest
    with _latest_lock:
        _latest_digest = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


# --- 数据收集 -----------------------------------------------------------------

def _collect_context(market_scope: str, session: Session, now: datetime) -> _DigestContext:
    settings = get_settings()
    lookback_hours = max(1, int(settings.digest_lookback_hours))
    cutoff = now - timedelta(hours=lookback_hours)

    market = None if market_scope == "all" else market_scope
    news_items = NewsRepository(session).list_recent(limit=120, market=market)

    recent = []
    for item in news_items:
        published = item.published_at
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if published >= cutoff:
            recent.append(item)

    recent_titles = [item.title for item in recent[:40]]

    sentiment_counts: dict[str, int] = {}
    for item in recent:
        label = item.sentiment_label or "unknown"
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1

    # 自选股命中：标题/摘要中命中自选股代码或名称即计入。
    watchlist_items = WatchlistRepository(session).list_all()
    if market is not None:
        watchlist_items = [w for w in watchlist_items if w.market == market]
    watchlist_hits: list[str] = []
    for item in recent:
        haystack = f"{item.title} {item.summary or ''}".lower()
        for w in watchlist_items:
            symbol_root = w.symbol.split(".")[0].lower()
            name = (w.display_name or "").lower()
            if (symbol_root and symbol_root in haystack) or (name and name in haystack):
                watchlist_hits.append(f"{w.display_name}（{w.symbol}）: {item.title}")
                break

    prompt = _build_prompt(market_scope, lookback_hours, recent_titles, watchlist_hits, sentiment_counts)
    return _DigestContext(
        market_scope=market_scope,
        lookback_hours=lookback_hours,
        total_news=len(recent),
        recent_titles=recent_titles,
        watchlist_hits=watchlist_hits,
        sentiment_counts=sentiment_counts,
        prompt=prompt,
    )


def _build_prompt(
    market_scope: str,
    lookback_hours: int,
    recent_titles: list[str],
    watchlist_hits: list[str],
    sentiment_counts: dict[str, int],
) -> str:
    label = _MARKET_LABELS.get(market_scope, market_scope)
    lines = [
        f"市场范围：{label}",
        f"回看时间窗：最近 {lookback_hours} 小时",
        f"新闻标题（{len(recent_titles)} 条）：",
    ]
    if recent_titles:
        lines.extend(f"- {title}" for title in recent_titles)
    else:
        lines.append("- （窗口内无新闻）")
    lines.append("自选股命中：")
    if watchlist_hits:
        lines.extend(f"- {hit}" for hit in watchlist_hits)
    else:
        lines.append("- （无自选股相关新闻）")
    sentiment_desc = "、".join(f"{k}:{v}" for k, v in sentiment_counts.items()) or "无"
    lines.append(f"情绪标签聚合：{sentiment_desc}")
    return "\n".join(lines)


# --- LLM 生成 -----------------------------------------------------------------

def _llm_sections(provider: Any, prompt: str) -> dict[str, str]:
    """调用 LLM 生成 4 段文本；任何异常都向上抛给 generate_digest 触发降级。"""
    result = provider.complete(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        operation_type="digest",
    )
    data = json.loads(result.content)
    if not isinstance(data, dict):
        raise ValueError("llm digest payload is not a json object")
    return {key: str(data.get(key) or "").strip() for key in _LLM_KEYS}


def _sections_from_llm(llm: dict[str, str], context: _DigestContext) -> list[DigestSection]:
    fallback = _rule_bodies(context)
    return [
        DigestSection(SECTION_OVERNIGHT, llm.get("overnight") or fallback["overnight"]),
        DigestSection(SECTION_WATCHLIST, llm.get("watchlist") or fallback["watchlist"]),
        DigestSection(SECTION_SENTIMENT, llm.get("sentiment") or fallback["sentiment"]),
        DigestSection(SECTION_RISK, llm.get("risk") or fallback["risk"]),
    ]


# --- 规则降级 -----------------------------------------------------------------

def _rule_bodies(context: _DigestContext) -> dict[str, str]:
    if context.recent_titles:
        overnight = f"过去 {context.lookback_hours} 小时共 {context.total_news} 条新闻，重点标题：\n" + "\n".join(
            f"- {title}" for title in context.recent_titles[:8]
        )
    else:
        overnight = f"过去 {context.lookback_hours} 小时窗口内暂无新增新闻。"

    if context.watchlist_hits:
        watchlist = "自选股相关新闻：\n" + "\n".join(f"- {hit}" for hit in context.watchlist_hits[:8])
    else:
        watchlist = "窗口内暂无与自选股直接相关的新闻。"

    if context.sentiment_counts:
        positive = context.sentiment_counts.get("positive", 0)
        negative = context.sentiment_counts.get("negative", 0)
        neutral = context.sentiment_counts.get("neutral", 0)
        if positive > negative:
            tone = "整体情绪偏多"
        elif negative > positive:
            tone = "整体情绪偏空"
        else:
            tone = "整体情绪中性/分歧"
        breakdown = "、".join(f"{k} {v} 条" for k, v in context.sentiment_counts.items())
        sentiment = f"{tone}（利好 {positive} / 利空 {negative} / 中性 {neutral}）。标签分布：{breakdown}。"
    else:
        sentiment = "窗口内新闻不足，暂无法判断整体情绪方向。"

    risk = "本简报由系统按规则自动汇总（LLM 未启用或暂不可用），仅供快速浏览，不构成投资建议；请结合实时行情与一手信息核实。"
    return {"overnight": overnight, "watchlist": watchlist, "sentiment": sentiment, "risk": risk}


def _rule_sections(context: _DigestContext) -> list[DigestSection]:
    bodies = _rule_bodies(context)
    return [
        DigestSection(SECTION_OVERNIGHT, bodies["overnight"]),
        DigestSection(SECTION_WATCHLIST, bodies["watchlist"]),
        DigestSection(SECTION_SENTIMENT, bodies["sentiment"]),
        DigestSection(SECTION_RISK, bodies["risk"]),
    ]


def _build_title(market_scope: str, now: datetime) -> str:
    label = _MARKET_LABELS.get(market_scope, market_scope)
    date_str = now.astimezone(UTC).strftime("%Y-%m-%d")
    return f"{label} · 每日 AI 简报 · {date_str}"


# --- 本地快照文件 -------------------------------------------------------------

def _resolve_data_dir() -> Path:
    """从 settings 的 database_url 推导 data 目录（与 sqlite 库同目录）。"""
    db_url = get_settings().database_url
    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        return Path(db_url[len(prefix):]).resolve().parent
    return Path(__file__).resolve().parents[2] / "data"


def _write_snapshot(digest: Digest) -> None:
    try:
        data_dir = _resolve_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = data_dir / "latest_digest.json"
        snapshot_path.write_text(
            json.dumps(digest.to_payload(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # 写失败只 log，绝不影响主流程
        logger.warning("failed to write latest_digest.json snapshot: %s", exc)


# --- 对外入口 -----------------------------------------------------------------

def generate_digest(
    market_scope: str,
    session: Session,
    *,
    provider_builder: Callable[[Any], Any] = build_provider,
    now: datetime | None = None,
) -> Digest:
    """生成一份简报：收集数据 -> LLM 生成（失败降级规则）-> 更新单例 -> 写快照。"""
    scope = market_scope if market_scope in _MARKET_LABELS else "all"
    current = now or _utc_now()
    context = _collect_context(scope, session, current)

    sections: list[DigestSection] | None = None
    generated_by = "rule"
    model_name: str | None = None

    config = LLMProviderConfigRepository(session).get_default()
    if config is not None:
        try:
            llm = _llm_sections(provider_builder(config), context.prompt)
            sections = _sections_from_llm(llm, context)
            generated_by = "llm"
            model_name = config.model_name
        except Exception as exc:  # LLM 不可用/返回异常 -> 优雅降级
            logger.warning("digest llm generation failed, falling back to rule-based summary: %s", exc)

    if sections is None:
        sections = _rule_sections(context)

    digest = Digest(
        title=_build_title(scope, current),
        market_scope=scope,
        generated_at=current,
        generated_by=generated_by,
        model_name=model_name,
        sections=sections,
    )
    set_latest_digest(digest)
    _write_snapshot(digest)
    return digest
