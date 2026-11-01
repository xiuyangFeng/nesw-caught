"""L1 粗筛：标题+摘要批量判断重要度、是否海外、是否值得精读，并给外文标题出中文译文。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.news_ai import STATUS_ERROR, STATUS_OK, NewsAiScreen
from app.models.news_item import NewsItem
from app.services.ai.context import PortfolioContext
from app.services.ai.llm_json import complete_json
from app.services.llm_providers import LLMProviderError

logger = logging.getLogger(__name__)

SUMMARY_MAX_CHARS = 200

SCREEN_SYSTEM_PROMPT = """你是 A 股投资者的新闻初筛助手。用户主做 A 股，同时关注美股、日韩等海外市场对 A 股的传导。
对每条新闻只看标题和摘要，给出：
- importance（0～3 的整数）：
  3 = 可能显著影响用户持仓/关注板块，或可能引发 A 股大盘明显波动的重大消息；
  2 = 与用户持仓、关注股、关注板块直接相关，或重要的宏观/海外市场消息；
  1 = 一般市场资讯；
  0 = 与投资无关或噪音。
- overseas（布尔）：事件主体发生在中国大陆和香港以外（如美国、日本、韩国、欧洲）。
- deep_read（布尔）：是否值得读全文判断对 A 股板块/个股的影响；importance ≥ 2 时通常为 true。
- title_zh：标题不是中文时给出简洁准确的中文译文；中文标题给 null。
- reason：一句话说明判断依据（中文，30 字以内）。
只返回 JSON：{"items": [{"id": 新闻编号, "importance": 0, "overseas": false, "deep_read": false, "title_zh": null, "reason": ""}]}，
每条输入新闻都必须有且只有一条结果。"""


@dataclass
class ScreenOutcome:
    screened: int = 0
    failed: int = 0
    exhausted: list[int] = field(default_factory=list)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_item(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    importance = raw.get("importance")
    if isinstance(importance, bool) or not isinstance(importance, int) or not 0 <= importance <= 3:
        return None
    overseas, deep_read = raw.get("overseas"), raw.get("deep_read")
    if not isinstance(overseas, bool) or not isinstance(deep_read, bool):
        return None
    title_zh = raw.get("title_zh")
    reason = raw.get("reason")
    return {
        "importance": importance,
        "overseas": overseas,
        "deep_read": deep_read,
        "title_zh": title_zh.strip() or None if isinstance(title_zh, str) else None,
        "reason": reason.strip()[:200] if isinstance(reason, str) else None,
    }


class NewsScreenService:
    def __init__(
        self,
        session: Session,
        provider,
        *,
        model_name: str,
        batch_size: int,
        lookback_hours: int,
        max_attempts: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.session = session
        self.provider = provider
        self.model_name = model_name
        self.batch_size = batch_size
        self.lookback_hours = lookback_hours
        self.max_attempts = max_attempts
        self.clock = clock

    def pending_news(self) -> list[NewsItem]:
        since = self.clock() - timedelta(hours=self.lookback_hours)
        stmt = (
            select(NewsItem)
            .outerjoin(NewsAiScreen, NewsAiScreen.news_id == NewsItem.id)
            .where(
                NewsItem.effective_at >= since,
                NewsItem.ingest_status == "ingested",
                or_(
                    NewsAiScreen.id.is_(None),
                    and_(NewsAiScreen.status == STATUS_ERROR, NewsAiScreen.attempts < self.max_attempts),
                ),
            )
            .order_by(NewsItem.effective_at.desc(), NewsItem.id.desc())
            .limit(self.batch_size)
        )
        return list(self.session.scalars(stmt))

    def screen_once(self, context: PortfolioContext) -> ScreenOutcome:
        items = self.pending_news()
        outcome = ScreenOutcome()
        if not items:
            return outcome

        try:
            payload = complete_json(
                self.provider,
                system=SCREEN_SYSTEM_PROMPT,
                user=self._user_prompt(items, context),
                operation_type="ai_screen",
            )
            raw_items = payload.get("items") if isinstance(payload, dict) else None
            error = None if isinstance(raw_items, list) else "missing items list"
        except LLMProviderError as exc:
            logger.warning("ai screen batch failed (%s items): %s", len(items), exc)
            raw_items, error = [], str(exc)[:500]

        parsed: dict[int, dict] = {}
        for raw in raw_items or []:
            news_id = raw.get("id") if isinstance(raw, dict) else None
            result = _parse_item(raw)
            if isinstance(news_id, int) and result is not None:
                parsed[news_id] = result

        existing = {
            row.news_id: row
            for row in self.session.scalars(
                select(NewsAiScreen).where(NewsAiScreen.news_id.in_([item.id for item in items]))
            )
        }
        now = self.clock()
        for item in items:
            row = existing.get(item.id)
            if row is None:
                row = NewsAiScreen(news_id=item.id, importance=0, overseas=False, deep_read=False, attempts=0)
                self.session.add(row)
            row.attempts = (row.attempts or 0) + 1
            row.model_name = self.model_name
            row.screened_at = now
            result = parsed.get(item.id)
            if result is not None:
                for key, value in result.items():
                    setattr(row, key, value)
                row.status, row.error = STATUS_OK, None
                outcome.screened += 1
                continue
            row.status = STATUS_ERROR
            row.error = error or "item missing or invalid in model output"
            outcome.failed += 1
            if row.attempts >= self.max_attempts:
                outcome.exhausted.append(item.id)
        self.session.flush()
        return outcome

    @staticmethod
    def _user_prompt(items: list[NewsItem], context: PortfolioContext) -> str:
        lines = [context.prompt_block(), "", "新闻列表："]
        for item in items:
            summary = (item.summary or "").strip().replace("\n", " ")
            if len(summary) > SUMMARY_MAX_CHARS:
                summary = summary[:SUMMARY_MAX_CHARS] + "…"
            source = f"{item.source_name}/{item.market}"
            lines.append(f"[{item.id}] ({source}) {item.title}" + (f" —— {summary}" if summary else ""))
        return "\n".join(lines)
