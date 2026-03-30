from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy.orm import Session

from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.schemas.news import NewsItemSummary
from app.schemas.watchlist import (
    ResearchActionLevel,
    ResearchDriverCategory,
    ResearchTopActionLevel,
    WatchlistResearchBriefView,
    WatchlistResearchDriverView,
)
from app.services.quote_service import QuoteService


WINDOW_DAYS = 14
MAX_DRIVERS_PER_CATEGORY = 2

POLICY_PATTERNS = (
    "policy",
    "regulator",
    "tariff",
    "export control",
    "guideline",
    "subsidy",
    "antitrust",
    "approval",
    "政策",
    "监管",
    "发改委",
    "工信部",
    "补贴",
    "禁令",
    "制裁",
    "审批",
)
COMPANY_PATTERNS = (
    "launch",
    "product",
    "order",
    "contract",
    "guidance",
    "earnings",
    "capex",
    "partnership",
    "订单",
    "合同",
    "产品",
    "发布",
    "指引",
    "财报",
    "扩产",
    "合作",
)
SUPPLY_CHAIN_PATTERNS = (
    "supply chain",
    "supplier",
    "upstream",
    "downstream",
    "demand",
    "pricing",
    "capacity",
    "产业链",
    "上游",
    "下游",
    "供应链",
    "需求",
    "涨价",
    "产能",
)
PRICE_ACTION_PATTERNS = (
    "surge",
    "rally",
    "drop",
    "tumbles",
    "jumps",
    "shares jump",
    "shares rose",
    "shares fell",
    "大涨",
    "大跌",
    "飙升",
    "暴跌",
    "股价异动",
)


@dataclass(frozen=True)
class ClassifiedDriver:
    category: ResearchDriverCategory
    action_level: ResearchActionLevel
    reason: str
    news_item: NewsItemSummary
    published_at: datetime


class WatchlistResearchService:
    def __init__(self, quote_service: QuoteService | None = None) -> None:
        self.quote_service = quote_service or QuoteService()

    def build_brief(self, symbol: str, session: Session) -> WatchlistResearchBriefView:
        quote = self.quote_service.get_cached_symbol_quote(symbol, session)
        resolved_symbol = str(quote["symbol"])
        news_items = NewsMentionsRepository(session).list_related_news(resolved_symbol)
        summaries = [NewsItemSummary.model_validate(item, from_attributes=True) for item in news_items]
        drivers = self._build_drivers(summaries)
        has_unexplained_price_move = bool(quote.get("is_abnormal")) and not any(
            driver.action_level in {"act_now", "watch_today"} for driver in drivers
        )
        top_action_level = self._top_action_level(drivers, has_unexplained_price_move)
        return WatchlistResearchBriefView(
            symbol=resolved_symbol,
            market=str(quote["market"]),
            generated_at=datetime.now(timezone.utc),
            window_days=WINDOW_DAYS,
            top_action_level=top_action_level,
            has_unexplained_price_move=has_unexplained_price_move,
            drivers=[
                WatchlistResearchDriverView(
                    category=driver.category,
                    action_level=driver.action_level,
                    reason=driver.reason,
                    news_item=driver.news_item,
                )
                for driver in drivers
            ],
        )

    def _build_drivers(self, items: list[NewsItemSummary]) -> list[ClassifiedDriver]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
        dedupe_keys: set[tuple[ResearchDriverCategory, str]] = set()
        per_category: dict[ResearchDriverCategory, int] = {}
        drivers: list[ClassifiedDriver] = []
        for item in items:
            published_at = item.published_at or item.fetched_at
            if published_at < cutoff:
                continue
            category = self._classify(item)
            if category is None:
                continue
            normalized_title = re.sub(r"\s+", " ", item.title.lower()).strip()
            dedupe_key = (category, normalized_title)
            if dedupe_key in dedupe_keys:
                continue
            if per_category.get(category, 0) >= MAX_DRIVERS_PER_CATEGORY:
                continue
            action_level = self._action_level(category, published_at)
            driver = ClassifiedDriver(
                category=category,
                action_level=action_level,
                reason=self._reason_text(category, action_level),
                news_item=item,
                published_at=published_at,
            )
            dedupe_keys.add(dedupe_key)
            per_category[category] = per_category.get(category, 0) + 1
            drivers.append(driver)
        return sorted(drivers, key=self._sort_key)

    def _classify(self, item: NewsItemSummary) -> ResearchDriverCategory | None:
        text = f"{item.title} {item.summary or ''}".lower()
        if self._matches(text, POLICY_PATTERNS):
            return "policy_macro"
        if self._matches(text, COMPANY_PATTERNS):
            return "company_action"
        if self._matches(text, SUPPLY_CHAIN_PATTERNS):
            return "supply_chain"
        if self._matches(text, PRICE_ACTION_PATTERNS):
            return "price_action"
        return None

    def _action_level(self, category: ResearchDriverCategory, published_at: datetime) -> ResearchActionLevel:
        age_days = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 86400)
        if category in {"policy_macro", "company_action"}:
            return "act_now" if age_days <= 7 else "watch_today"
        if category == "supply_chain":
            return "watch_today"
        if category == "price_action":
            return "watch_today" if age_days <= 3 else "know_only"
        return "know_only"

    def _reason_text(self, category: ResearchDriverCategory, action_level: ResearchActionLevel) -> str:
        category_reason = {
            "policy_macro": "政策或监管信号直接影响该标的的中期预期。",
            "company_action": "公司动作或订单变化可能改变未来催化节奏。",
            "supply_chain": "产业链供需或价格变化值得继续跟踪传导路径。",
            "price_action": "股价异动需要结合更多信息确认是否具备持续性。",
        }[category]
        action_reason = {
            "act_now": "优先级高，建议立即核对原文。",
            "watch_today": "有跟踪价值，建议今天内完成确认。",
            "know_only": "可作为背景信息保留观察。",
        }[action_level]
        return f"{category_reason}{action_reason}"

    def _top_action_level(self, drivers: list[ClassifiedDriver], has_unexplained_price_move: bool) -> ResearchTopActionLevel:
        if not drivers:
            return "none"
        if any(driver.action_level == "act_now" for driver in drivers):
            return "act_now"
        if has_unexplained_price_move or any(driver.action_level == "watch_today" for driver in drivers):
            return "watch_today"
        if any(driver.action_level == "know_only" for driver in drivers):
            return "know_only"
        return "none"

    def _matches(self, text: str, patterns: tuple[str, ...]) -> bool:
        return any(pattern in text for pattern in patterns)

    def _sort_key(self, driver: ClassifiedDriver) -> tuple[int, float]:
        action_rank = {"act_now": 0, "watch_today": 1, "know_only": 2}[driver.action_level]
        return (action_rank, -driver.published_at.timestamp())
