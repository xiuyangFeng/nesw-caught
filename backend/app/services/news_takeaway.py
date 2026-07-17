"""高编辑分新闻的「一句话结论」补齐服务。

feed layout 构建时把缺 takeaway 的高分新闻 id 入队(enqueue_takeaway_candidates),
TakeawayWorker 后台批量调 LLM 生成并写回 news_item.ai_takeaway;一条新闻只生成一次。
无 LLM 配置时降级为结构化规则摘要（主体/事件/影响对象）。
"""
from __future__ import annotations

import logging
import queue

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import build_provider
from app.services.news_structured_summary import build_structured_takeaway

logger = logging.getLogger(__name__)

# 全局内存补齐队列(与 queue_worker.analysis_queue 同模式)
takeaway_queue: queue.Queue[list[int]] = queue.Queue()

TAKEAWAY_MAX_LEN = 120


def enqueue_takeaway_candidates(news_ids: list[int]) -> None:
    if news_ids:
        takeaway_queue.put(news_ids)


class NewsTakeawayService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.config_repository = LLMProviderConfigRepository(session)

    def generate_for_ids(self, news_ids: list[int], *, batch_limit: int) -> list[NewsItem]:
        """为缺 takeaway 的新闻生成一句话结论,返回成功写回的条目(不 commit,由调用方决定)。"""
        if not news_ids or batch_limit <= 0:
            return []

        stmt = (
            select(NewsItem)
            .where(NewsItem.id.in_(news_ids), NewsItem.ai_takeaway.is_(None))
            .order_by(NewsItem.id)
            .limit(batch_limit)
        )
        items = list(self.session.scalars(stmt))
        config = self.config_repository.get_active()
        if config is None:
            # 无 LLM 时降级为结构化规则摘要（主体/事件/影响对象）
            updated: list[NewsItem] = []
            for item in items:
                takeaway = build_structured_takeaway(title=item.title, summary=item.summary)
                item.ai_takeaway = (takeaway[:TAKEAWAY_MAX_LEN] if takeaway else "")
                updated.append(item)
            return updated

        updated = []
        for item in items:
            prompt = "\n".join(
                [
                    f"Title: {item.title}",
                    f"Summary: {item.summary or ''}",
                    f"Market: {item.market}",
                    "You write one-line conclusions for stock-market news readers.",
                    "Return JSON only with keys: takeaway.",
                    "takeaway: 一句中文结论(<=60字),说明谁受影响、偏利好还是利空、原因;无法判断时返回空字符串。",
                ]
            )
            try:
                payload = build_provider(config).analyze_json(prompt=prompt)
            except Exception as exc:
                # 单条失败保留 NULL，便于后续重试；不中断批次
                logger.warning("takeaway generation failed for news %s: %s", item.id, exc)
                continue
            # 只要拿到 LLM 响应就落库并计数(含空字符串「无法判断」),避免 NULL 残留导致下次
            # feed layout 重建再次入队、反复调用且不受日配额约束;前端对空值自动回退原文摘要。
            takeaway = str(payload.get("takeaway") or "").strip() if isinstance(payload, dict) else ""
            item.ai_takeaway = takeaway[:TAKEAWAY_MAX_LEN] if takeaway else ""
            updated.append(item)
        return updated
