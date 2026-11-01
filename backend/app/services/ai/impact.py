"""L2 精读：全文 → 中文摘要、明确看法、是否重大事件、对 A 股板块/个股的结构化影响。

用户修正（``replace_impacts_by_user``）整表替换某条新闻的影响，并记一条
``ImpactCorrection``；最近若干条修正会作为示例放进后续 L2 的 prompt，逐步沉淀为
用户自己的"传导规则"。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_ai import (
    DIRECTIONS,
    SOURCE_AI,
    SOURCE_USER,
    STATUS_ERROR,
    STATUS_OK,
    STRENGTHS,
    TARGET_SECTOR,
    TARGET_STOCK,
    ImpactCorrection,
    NewsAiAnalysis,
    NewsAiScreen,
    NewsImpact,
)
from app.models.news_item import NewsItem
from app.services.ai.context import PortfolioContext
from app.services.ai.llm_json import complete_json
from app.services.llm_providers import LLMProviderError

logger = logging.getLogger(__name__)

MAX_IMPACTS = 8
QUOTA_TZ = ZoneInfo("Asia/Shanghai")

IMPACT_SYSTEM_PROMPT = """你是 A 股投资者的新闻精读助手。用户主做 A 股，关注海外（美股、日韩等）消息对 A 股的传导。
阅读新闻全文，判断它对 A 股板块和个股的影响，并给出明确看法（不要模棱两可）。
- summary_zh：中文摘要，80 字以内；
- view：明确看法，60 字以内，说清楚利好/利空谁、程度、需要关注什么；
- major：是否属于需要立即知道的重大事件（如美联储意外决议、龙头公司业绩巨幅超预期/暴雷、重大政策、地缘冲突升级）；
- impacts：最多 8 条，每条
  {"target_type": "stock" 或 "sector", "code": 股票代码（A 股 6 位、港股 5 位，板块为 null）, "name": 名称,
   "direction": "bullish" | "bearish" | "neutral", "strength": "strong" | "medium" | "weak", "rationale": 30 字以内的理由}。
  板块名称用东方财富行业/概念板块的叫法；若涉及用户的关注板块，直接沿用其名称。
  优先判断对用户持仓与关注股的影响；没有实质影响时 impacts 返回空数组。
参考"用户修正示例"：它们代表用户对传导关系的判断，遇到相似新闻按用户的思路判断。
只返回 JSON：{"summary_zh": "", "view": "", "major": false, "impacts": []}"""


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ImpactOutcome:
    news: NewsItem
    screen: NewsAiScreen | None
    analysis: NewsAiAnalysis
    impacts: list[NewsImpact] = field(default_factory=list)
    ok: bool = False
    exhausted: bool = False
    # 用户已修正过该新闻的影响：精读只更新文字结论，不覆盖影响、不再发提醒。
    user_corrected: bool = False


def _clean_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] or None


def parse_impact(raw: object, context: PortfolioContext | None = None) -> dict | None:
    """校验并规整一条影响；不合法返回 None。股票代码尽量归一到自选股的写法。"""
    if not isinstance(raw, dict):
        return None
    target_type = raw.get("target_type")
    direction = raw.get("direction")
    strength = raw.get("strength")
    name = _clean_text(raw.get("name"), 128)
    if target_type not in (TARGET_STOCK, TARGET_SECTOR) or direction not in DIRECTIONS or strength not in STRENGTHS:
        return None
    if name is None:
        return None
    code = _clean_text(raw.get("code"), 32)
    if target_type == TARGET_SECTOR:
        code = None
    elif context is not None:
        stock = context.find_stock(code, name)
        if stock is not None:
            code, name = stock.symbol, stock.name
    if target_type == TARGET_STOCK and code:
        code = code.upper()
    return {
        "target_type": target_type,
        "target_code": code,
        "target_name": name,
        "direction": direction,
        "strength": strength,
        "rationale": _clean_text(raw.get("rationale"), 200),
    }


def impact_to_dict(impact: NewsImpact) -> dict:
    return {
        "target_type": impact.target_type,
        "code": impact.target_code,
        "name": impact.target_name,
        "direction": impact.direction,
        "strength": impact.strength,
        "rationale": impact.rationale,
    }


class NewsImpactService:
    def __init__(
        self,
        session: Session,
        provider,
        *,
        model_name: str,
        daily_limit: int,
        min_importance: int,
        max_attempts: int,
        body_max_chars: int,
        correction_examples: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.session = session
        self.provider = provider
        self.model_name = model_name
        self.daily_limit = daily_limit
        self.min_importance = min_importance
        self.max_attempts = max_attempts
        self.body_max_chars = body_max_chars
        self.correction_examples = correction_examples
        self.clock = clock

    # ------------------------------------------------------------------ 选题

    def analyzed_today(self) -> int:
        local_day = self.clock().astimezone(QUOTA_TZ).date()
        start = datetime.combine(local_day, time.min, tzinfo=QUOTA_TZ).astimezone(UTC)
        return int(
            self.session.scalar(
                select(func.count()).select_from(NewsAiAnalysis).where(NewsAiAnalysis.analyzed_at >= start)
            )
            or 0
        )

    def pending_news(self, *, limit: int) -> list[NewsItem]:
        remaining = max(0, self.daily_limit - self.analyzed_today())
        limit = min(limit, remaining)
        if limit <= 0:
            return []
        stmt = (
            select(NewsItem)
            .join(NewsAiScreen, NewsAiScreen.news_id == NewsItem.id)
            .outerjoin(NewsAiAnalysis, NewsAiAnalysis.news_id == NewsItem.id)
            .where(
                NewsAiScreen.status == STATUS_OK,
                NewsAiScreen.deep_read.is_(True),
                NewsAiScreen.importance >= self.min_importance,
                or_(
                    NewsAiAnalysis.id.is_(None),
                    and_(NewsAiAnalysis.status == STATUS_ERROR, NewsAiAnalysis.attempts < self.max_attempts),
                ),
            )
            .order_by(NewsAiScreen.importance.desc(), NewsItem.effective_at.desc(), NewsItem.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    # ------------------------------------------------------------------ 精读

    def analyze_pending(self, context: PortfolioContext, *, limit: int) -> list[ImpactOutcome]:
        items = self.pending_news(limit=limit)
        if not items:
            return []
        examples = self._examples_block()
        return [self._analyze(item, context, examples) for item in items]

    def _analyze(self, item: NewsItem, context: PortfolioContext, examples: str) -> ImpactOutcome:
        screen = self.session.scalar(select(NewsAiScreen).where(NewsAiScreen.news_id == item.id))
        analysis = self.session.scalar(select(NewsAiAnalysis).where(NewsAiAnalysis.news_id == item.id))
        if analysis is None:
            analysis = NewsAiAnalysis(news_id=item.id, major=False, attempts=0)
            self.session.add(analysis)
        analysis.attempts = (analysis.attempts or 0) + 1
        analysis.model_name = self.model_name
        analysis.analyzed_at = self.clock()
        outcome = ImpactOutcome(news=item, screen=screen, analysis=analysis)

        try:
            payload = complete_json(
                self.provider,
                system=IMPACT_SYSTEM_PROMPT,
                user=self._user_prompt(item, screen, context, examples),
                operation_type="ai_impact",
            )
            parsed = self._parse(payload, context)
        except (LLMProviderError, ValueError) as exc:
            logger.warning("ai impact failed for news %s: %s", item.id, exc)
            analysis.status, analysis.error = STATUS_ERROR, str(exc)[:500]
            outcome.exhausted = analysis.attempts >= self.max_attempts
            self.session.flush()
            return outcome

        analysis.summary_zh = parsed["summary_zh"]
        analysis.view = parsed["view"]
        analysis.major = parsed["major"]
        analysis.status, analysis.error = STATUS_OK, None
        outcome.ok = True
        corrected = self.session.scalar(
            select(ImpactCorrection.id).where(ImpactCorrection.news_id == item.id).limit(1)
        )
        if corrected is not None:
            outcome.user_corrected = True
            self.session.flush()
            return outcome
        self.session.execute(
            delete(NewsImpact).where(NewsImpact.news_id == item.id, NewsImpact.source == SOURCE_AI)
        )
        for impact in parsed["impacts"]:
            row = NewsImpact(news_id=item.id, source=SOURCE_AI, created_at=self.clock(), **impact)
            self.session.add(row)
            outcome.impacts.append(row)
        self.session.flush()
        return outcome

    @staticmethod
    def _parse(payload: object, context: PortfolioContext) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("model output is not an object")
        summary = _clean_text(payload.get("summary_zh"), 400)
        view = _clean_text(payload.get("view"), 300)
        major = payload.get("major")
        raw_impacts = payload.get("impacts")
        if summary is None or view is None or not isinstance(major, bool) or not isinstance(raw_impacts, list):
            raise ValueError("model output missing summary_zh/view/major/impacts")
        impacts: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for raw in raw_impacts:
            impact = parse_impact(raw, context)
            if impact is None:
                continue
            key = (impact["target_type"], impact["target_code"] or impact["target_name"])
            if key in seen:
                continue
            seen.add(key)
            impacts.append(impact)
            if len(impacts) >= MAX_IMPACTS:
                break
        return {"summary_zh": summary, "view": view, "major": major, "impacts": impacts}

    def _body(self, item: NewsItem) -> str:
        content = self.session.scalar(select(ArticleContent.content_text).where(ArticleContent.news_id == item.id))
        text = (content or item.summary or "").strip()
        return text[: self.body_max_chars]

    def _examples_block(self) -> str:
        if self.correction_examples <= 0:
            return ""
        rows = self.session.scalars(
            select(ImpactCorrection).order_by(ImpactCorrection.created_at.desc()).limit(self.correction_examples)
        ).all()
        if not rows:
            return ""
        lines = ["用户修正示例（新的在前）："]
        for row in rows:
            lines.append(f"- 新闻：{row.news_title}")
            lines.append(f"  AI 原判：{row.before_json}")
            lines.append(f"  用户修正：{row.after_json}")
            if row.note:
                lines.append(f"  用户说明：{row.note}")
        return "\n".join(lines)

    def _user_prompt(
        self, item: NewsItem, screen: NewsAiScreen | None, context: PortfolioContext, examples: str
    ) -> str:
        title = item.title
        if screen is not None and screen.title_zh:
            title = f"{item.title}（译：{screen.title_zh}）"
        parts = [
            context.prompt_block(),
            "",
            f"新闻标题：{title}",
            f"来源：{item.source_name}（{item.market}）",
            f"正文：\n{self._body(item)}",
        ]
        if examples:
            parts.extend(["", examples])
        return "\n".join(parts)


def replace_impacts_by_user(
    session: Session,
    news_id: int,
    impacts: list[dict],
    *,
    note: str | None = None,
    context: PortfolioContext | None = None,
) -> list[NewsImpact]:
    """用户修正：整表替换该新闻的影响，并记录修正（作为后续 L2 示例）。不合法的条目直接报错。"""
    item = session.get(NewsItem, news_id)
    if item is None:
        raise LookupError(f"news {news_id} not found")
    parsed: list[dict] = []
    for raw in impacts:
        impact = parse_impact(raw, context)
        if impact is None:
            raise ValueError(f"invalid impact: {raw!r}")
        parsed.append(impact)

    existing = session.scalars(select(NewsImpact).where(NewsImpact.news_id == news_id).order_by(NewsImpact.id)).all()
    before = [impact_to_dict(row) for row in existing]
    session.execute(delete(NewsImpact).where(NewsImpact.news_id == news_id))
    rows = [NewsImpact(news_id=news_id, source=SOURCE_USER, **impact) for impact in parsed]
    session.add_all(rows)
    session.add(
        ImpactCorrection(
            news_id=news_id,
            news_title=item.title,
            before_json=json.dumps(before, ensure_ascii=False),
            after_json=json.dumps([impact_to_dict(row) for row in rows], ensure_ascii=False),
            note=(note or "").strip()[:500] or None,
        )
    )
    session.flush()
    return rows
