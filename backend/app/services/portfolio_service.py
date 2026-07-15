from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.repositories.market_repository import MarketRepository
from app.repositories.news_mentions_repository import NewsMentionsRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import NewsItemSummary
from app.schemas.portfolio import (
    PortfolioPositionView,
    PortfolioSummaryView,
    PortfolioWeightedNewsView,
)
from app.services.quote_provider import normalize_symbol

# 加权新闻只看最近这些天内命中的新闻，避免历史噪声压过当下最该看的消息。
_NEWS_WINDOW_DAYS = 7
# 组合层最多返回多少条“最该看”的加权新闻。
_MAX_WEIGHTED_NEWS = 12


class PortfolioService:
    """持仓 / 组合视图：读所有有持仓的自选股，结合最新行情算成本、盈亏，
    并按仓位价值加权聚合命中新闻，得到组合层“最该看”的新闻排序。

    纯读 + 计算：缺行情、缺成本、缺持仓均优雅降级，不抛错。
    """

    def build_summary(self, session: Session) -> PortfolioSummaryView:
        now = datetime.now(UTC)
        holdings = self._load_holdings(session)
        if not holdings:
            return PortfolioSummaryView(generated_at=now)

        snapshots = self._load_snapshots(session, holdings)

        positions: list[_PositionCalc] = []
        for item in holdings:
            positions.append(self._build_position(item, snapshots.get(id(item))))

        total_market_value = sum(p.market_value for p in positions if p.market_value is not None)
        total_cost_basis = sum(p.cost_basis for p in positions if p.cost_basis is not None)
        # 只对“既有行情又有成本”的持仓聚合盈亏，避免口径不一致。
        total_unrealized_pnl = sum(
            p.unrealized_pnl for p in positions if p.unrealized_pnl is not None
        )
        total_pnl_percent: float | None = None
        pnl_cost_basis = sum(
            p.cost_basis
            for p in positions
            if p.cost_basis is not None and p.unrealized_pnl is not None
        )
        if pnl_cost_basis > 0:
            total_pnl_percent = round(total_unrealized_pnl / pnl_cost_basis * 100, 4)

        weights = self._compute_weights(positions, total_market_value, total_cost_basis)
        for position, weight in zip(positions, weights, strict=True):
            position.weight = weight

        weighted_news = self._build_weighted_news(session, positions, now)

        return PortfolioSummaryView(
            generated_at=now,
            position_count=len(positions),
            priced_position_count=sum(1 for p in positions if p.market_value is not None),
            total_market_value=round(total_market_value, 4),
            total_cost_basis=round(total_cost_basis, 4),
            total_unrealized_pnl=round(total_unrealized_pnl, 4),
            total_unrealized_pnl_percent=total_pnl_percent,
            positions=[p.to_view() for p in positions],
            weighted_news=weighted_news,
        )

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------
    def _load_holdings(self, session: Session) -> list[WatchlistItem]:
        items = WatchlistRepository(session).list_all()
        # 只保留“有持仓”的自选股：position_size 非空且为正。
        return [
            item
            for item in items
            if item.position_size is not None and item.position_size > 0
        ]

    def _lookup_symbol(self, item: WatchlistItem) -> str:
        """把自选股存储 symbol 归一化为行情快照使用的规范 symbol。"""
        try:
            return normalize_symbol(item.symbol, item.market).symbol
        except ValueError:
            return item.symbol

    def _load_snapshots(
        self, session: Session, holdings: list[WatchlistItem]
    ) -> dict[int, PriceSnapshot]:
        market_repo = MarketRepository(session)
        lookup_by_item: dict[int, str] = {id(item): self._lookup_symbol(item) for item in holdings}
        unique_symbols = list(dict.fromkeys(lookup_by_item.values()))
        latest = market_repo.list_latest_by_symbols(unique_symbols)
        return {
            item_id: latest[symbol]
            for item_id, symbol in lookup_by_item.items()
            if symbol in latest
        }

    # ------------------------------------------------------------------
    # 单只持仓计算
    # ------------------------------------------------------------------
    def _build_position(
        self, item: WatchlistItem, snapshot: PriceSnapshot | None
    ) -> _PositionCalc:
        position_size = float(item.position_size or 0.0)
        average_cost = float(item.average_cost) if item.average_cost is not None else None

        price: float | None = None
        change_percent: float | None = None
        price_status = "unavailable"
        price_message: str | None = "quote not produced yet"
        quote_fetched_at: datetime | None = None
        if snapshot is not None:
            quote_fetched_at = snapshot.fetched_at
            change_percent = snapshot.change_percent
            price_status = snapshot.quote_status or "ok"
            price_message = snapshot.status_message
            # price 为非空 Float，抓取失败时被落成 0.0；此处把 0.0 视为无有效价格。
            if snapshot.price:
                price = snapshot.price
            else:
                price = None
                if price_status == "ok":
                    price_status = "unavailable"
                price_message = price_message or "quote unavailable"

        market_value = round(position_size * price, 4) if price is not None else None
        cost_basis = round(position_size * average_cost, 4) if average_cost is not None else None

        unrealized_pnl: float | None = None
        unrealized_pnl_percent: float | None = None
        if market_value is not None and cost_basis is not None:
            unrealized_pnl = round(market_value - cost_basis, 4)
            if cost_basis > 0:
                unrealized_pnl_percent = round(unrealized_pnl / cost_basis * 100, 4)

        return _PositionCalc(
            item=item,
            position_size=position_size,
            average_cost=average_cost,
            current_price=price,
            change_percent=change_percent,
            price_status=price_status,
            price_message=price_message,
            quote_fetched_at=quote_fetched_at,
            market_value=market_value,
            cost_basis=cost_basis,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
        )

    # ------------------------------------------------------------------
    # 权重
    # ------------------------------------------------------------------
    def _compute_weights(
        self,
        positions: list[_PositionCalc],
        total_market_value: float,
        total_cost_basis: float,
    ) -> list[float]:
        """按仓位价值计算权重（0~1）。优先按市值；缺行情时退化为按成本；
        再缺则按持仓数量等价，最后等权兜底，保证加权新闻始终可算。"""
        if total_market_value > 0:
            return [
                (p.market_value / total_market_value) if p.market_value is not None else 0.0
                for p in positions
            ]
        if total_cost_basis > 0:
            return [
                (p.cost_basis / total_cost_basis) if p.cost_basis is not None else 0.0
                for p in positions
            ]
        total_size = sum(p.position_size for p in positions)
        if total_size > 0:
            return [p.position_size / total_size for p in positions]
        count = len(positions)
        return [1.0 / count for _ in positions] if count else []

    # ------------------------------------------------------------------
    # 按仓位加权的新闻排序
    # ------------------------------------------------------------------
    def _build_weighted_news(
        self,
        session: Session,
        positions: list[_PositionCalc],
        now: datetime,
    ) -> list[PortfolioWeightedNewsView]:
        mentions_repo = NewsMentionsRepository(session)
        window_start = now - timedelta(days=_NEWS_WINDOW_DAYS)
        aggregated: dict[int, _NewsAggregate] = {}

        for position in positions:
            weight = position.weight or 0.0
            if weight <= 0:
                continue
            symbol = position.item.symbol
            for news in mentions_repo.list_related_news(symbol):
                if news.sentiment_score is None:
                    continue
                if not self._is_recent(news, window_start):
                    continue
                entry = aggregated.get(news.id)
                if entry is None:
                    entry = _NewsAggregate(news=news)
                    aggregated[news.id] = entry
                entry.signed_impact += news.sentiment_score * weight
                entry.symbols.add(symbol)

        ranked = [entry for entry in aggregated.values() if entry.signed_impact != 0.0]
        ranked.sort(key=lambda e: (abs(e.signed_impact), self._sort_time(e.news)), reverse=True)

        return [
            PortfolioWeightedNewsView(
                news_item=NewsItemSummary.model_validate(entry.news, from_attributes=True),
                symbols=sorted(entry.symbols),
                sentiment_score=entry.news.sentiment_score,
                signed_impact=round(entry.signed_impact, 6),
                impact_score=round(abs(entry.signed_impact), 6),
            )
            for entry in ranked[:_MAX_WEIGHTED_NEWS]
        ]

    def _is_recent(self, news: NewsItem, window_start: datetime) -> bool:
        moment = news.published_at or news.fetched_at
        if moment is None:
            return False
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment >= window_start

    def _sort_time(self, news: NewsItem) -> datetime:
        moment = news.published_at or news.fetched_at
        if moment is None:
            return datetime.min.replace(tzinfo=UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment


class _PositionCalc:
    """服务内部使用的可变持仓计算载体（最后再转成 Pydantic view）。"""

    def __init__(
        self,
        *,
        item: WatchlistItem,
        position_size: float,
        average_cost: float | None,
        current_price: float | None,
        change_percent: float | None,
        price_status: str,
        price_message: str | None,
        quote_fetched_at: datetime | None,
        market_value: float | None,
        cost_basis: float | None,
        unrealized_pnl: float | None,
        unrealized_pnl_percent: float | None,
    ) -> None:
        self.item = item
        self.position_size = position_size
        self.average_cost = average_cost
        self.current_price = current_price
        self.change_percent = change_percent
        self.price_status = price_status
        self.price_message = price_message
        self.quote_fetched_at = quote_fetched_at
        self.market_value = market_value
        self.cost_basis = cost_basis
        self.unrealized_pnl = unrealized_pnl
        self.unrealized_pnl_percent = unrealized_pnl_percent
        self.weight: float | None = None

    def to_view(self) -> PortfolioPositionView:
        return PortfolioPositionView(
            symbol=self.item.symbol,
            market=self.item.market,
            display_name=self.item.display_name,
            position_size=self.position_size,
            average_cost=self.average_cost,
            current_price=self.current_price,
            change_percent=self.change_percent,
            price_status=self.price_status,
            price_message=self.price_message,
            quote_fetched_at=self.quote_fetched_at,
            market_value=self.market_value,
            cost_basis=self.cost_basis,
            unrealized_pnl=self.unrealized_pnl,
            unrealized_pnl_percent=self.unrealized_pnl_percent,
            weight=round(self.weight, 6) if self.weight is not None else None,
        )


class _NewsAggregate:
    def __init__(self, *, news: NewsItem) -> None:
        self.news = news
        self.signed_impact: float = 0.0
        self.symbols: set[str] = set()
