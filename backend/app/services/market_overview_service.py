"""市场总览 - 指数报价刷新与查询编排服务（计划任务 B3）。

设计契约：docs/superpowers/specs/2026-08-02-market-overview-design.md。

关键纪律：
- 指数 ticker（``^GSPC``/``^VIX``/``000300.SS`` 等）**不经过 normalize_symbol**
  （``^`` 会被抛 ValueError，``.SS`` 会被改写成 ``.SH`` 进而路由到腾讯源），
  这里按配置表直接构造 ``NormalizedSymbol(symbol=原始ticker, market=配置市场,
  provider_symbol=原始ticker)``，调 ``YahooFinanceQuoteProvider.fetch_quotes_batch``；
- "先联网后写库"两阶段纪律（对齐 ``QuoteService.refresh_watchlist_quotes``）：
  批量抓取全部完成后才开写事务，``MarketRepository.save_snapshot`` 批量 flush +
  单次 commit，provider 失败行不回写；
- 配置表为空时回落内置默认清单（``DEFAULT_INDEX_CONFIGS``，含 ^VIX 与 kind=etf
  条目），保证全新部署开箱可用（迁移不 seed 数据，见设计文档四节）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_overview_repository import MarketOverviewRepository
from app.repositories.market_repository import MarketRepository
from app.services.quote_provider import (
    NormalizedSymbol,
    QuoteRecord,
    YahooFinanceQuoteProvider,
)

logger = logging.getLogger(__name__)

# ^VIX 作为 us 市场的一条 kind=index 配置入表（用户可删可禁用），代码按此常量
# 识别其在量化情绪计算中的特殊角色：不参与指数行展示，只提供 VIX 输入
# （设计文档十三.1 定案）。
VIX_SYMBOL = "^VIX"

# overview 固定五市场骨架（顺序即展示顺序），与 market_sentiment_service.TARGET_MARKETS 对齐。
OVERVIEW_MARKETS: tuple[str, ...] = ("us", "cn", "kr", "jp", "eu")

MARKET_DISPLAY_NAMES: dict[str, str] = {
    "us": "美股",
    "cn": "A股",
    "kr": "韩国",
    "jp": "日本",
    "eu": "欧洲",
}


@dataclass(frozen=True, slots=True)
class IndexConfigEntry:
    """配置表条目（或内置默认清单条目）的统一只读视图。"""

    symbol: str
    market: str
    display_name: str
    kind: str = "index"
    sort_order: int = 0


# 内置默认清单（设计文档四节定案）：配置表为空时生效。
DEFAULT_INDEX_CONFIGS: tuple[IndexConfigEntry, ...] = (
    IndexConfigEntry(symbol="^GSPC", market="us", display_name="标普500", kind="index", sort_order=0),
    IndexConfigEntry(symbol="^IXIC", market="us", display_name="纳斯达克", kind="index", sort_order=1),
    IndexConfigEntry(symbol=VIX_SYMBOL, market="us", display_name="恐慌指数", kind="index", sort_order=2),
    IndexConfigEntry(symbol="000300.SS", market="cn", display_name="沪深300", kind="index", sort_order=0),
    IndexConfigEntry(symbol="000001.SS", market="cn", display_name="上证指数", kind="index", sort_order=1),
    IndexConfigEntry(symbol="^KS11", market="kr", display_name="韩国KOSPI", kind="index", sort_order=0),
    IndexConfigEntry(symbol="^N225", market="jp", display_name="日经225", kind="index", sort_order=0),
    IndexConfigEntry(symbol="^STOXX50E", market="eu", display_name="欧洲斯托克50", kind="index", sort_order=0),
    IndexConfigEntry(symbol="^GDAXI", market="eu", display_name="德国DAX", kind="index", sort_order=1),
    IndexConfigEntry(symbol="XLK", market="us", display_name="科技ETF", kind="etf", sort_order=10),
    IndexConfigEntry(symbol="XLE", market="us", display_name="能源ETF", kind="etf", sort_order=11),
    IndexConfigEntry(symbol="XLF", market="us", display_name="金融ETF", kind="etf", sort_order=12),
    IndexConfigEntry(symbol="FEZ", market="eu", display_name="欧洲蓝筹ETF", kind="etf", sort_order=10),
)


@dataclass(frozen=True, slots=True)
class IndexQuoteRow:
    """配置条目 join 最新快照的展示行（/api/market/overview 指数区与 ETF 板块区共用）。"""

    symbol: str
    market: str
    display_name: str
    kind: str
    sort_order: int
    price: float | None
    change_percent: float | None
    previous_close: float | None
    status: str  # 快照的 quote_status；无快照时 "unavailable"
    fetched_at: datetime | None


class MarketOverviewService:
    """市场总览编排：指数报价刷新（写路径）与配置 join 快照查询（读路径）。"""

    def __init__(self, provider: YahooFinanceQuoteProvider | None = None) -> None:
        self.provider = provider or YahooFinanceQuoteProvider()

    def list_enabled_entries(self, session: Session) -> list[IndexConfigEntry]:
        """enabled 配置条目；配置表为空时回落内置默认清单。"""
        rows = MarketOverviewRepository(session).list_enabled()
        if not rows:
            return list(DEFAULT_INDEX_CONFIGS)
        return [
            IndexConfigEntry(
                symbol=row.symbol,
                market=row.market,
                display_name=row.display_name,
                kind=row.kind,
                sort_order=row.sort_order,
            )
            for row in rows
        ]

    def refresh_index_quotes(self, session: Session) -> list[QuoteRecord]:
        """刷新全部 enabled 指数/ETF 报价并落 price_snapshot。

        两阶段纪律：阶段一只联网（一次 ``fetch_quotes_batch``，provider 内部
        yf.download 批量 + 逐票回退），阶段二只写库（批量 flush + 单次 commit）。
        provider 返回的 fetch_failed 行不回写。
        """
        entries = self.list_enabled_entries(session)
        if not entries:
            return []

        normalized_list = [
            NormalizedSymbol(symbol=entry.symbol, market=entry.market, provider_symbol=entry.symbol)
            for entry in entries
        ]

        # 阶段一：只联网，不写库。
        records = self.provider.fetch_quotes_batch(normalized_list)

        # 阶段二：只写库，不联网（单次 commit 收敛写事务窗口）。
        market_repo = MarketRepository(session)
        for record in records:
            if record.status != "ok" or record.price is None:
                continue
            market_repo.save_snapshot(
                PriceSnapshot(
                    symbol=record.symbol,
                    market=record.market,
                    price=record.price,
                    change_amount=record.change_amount,
                    change_percent=record.change_percent,
                    open_price=record.open_price,
                    previous_close=record.previous_close,
                    day_high=record.day_high,
                    day_low=record.day_low,
                    volume=record.volume,
                    provider_name=record.source,
                    provider_symbol=record.provider_symbol,
                    quote_status=record.status,
                    status_message=record.message,
                    fetched_at=record.fetched_at,
                )
            )
        session.commit()
        return records

    def list_index_quotes(self, session: Session) -> list[IndexQuoteRow]:
        """配置条目 join 最新快照（无快照的条目 status="unavailable" 占位）。"""
        entries = self.list_enabled_entries(session)
        if not entries:
            return []
        snapshots = MarketRepository(session).list_latest_by_symbols(
            [entry.symbol for entry in entries]
        )
        rows: list[IndexQuoteRow] = []
        for entry in entries:
            snapshot = snapshots.get(entry.symbol)
            if snapshot is None:
                rows.append(
                    IndexQuoteRow(
                        symbol=entry.symbol,
                        market=entry.market,
                        display_name=entry.display_name,
                        kind=entry.kind,
                        sort_order=entry.sort_order,
                        price=None,
                        change_percent=None,
                        previous_close=None,
                        status="unavailable",
                        fetched_at=None,
                    )
                )
                continue
            rows.append(
                IndexQuoteRow(
                    symbol=entry.symbol,
                    market=entry.market,
                    display_name=entry.display_name,
                    kind=entry.kind,
                    sort_order=entry.sort_order,
                    price=snapshot.price,
                    change_percent=snapshot.change_percent,
                    previous_close=snapshot.previous_close,
                    status=snapshot.quote_status or "ok",
                    fetched_at=snapshot.fetched_at,
                )
            )
        return rows
