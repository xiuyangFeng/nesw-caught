"""关注板块与个股板块推断。

关注板块 = 启用中的自选股（含持仓）的 ``StockSector`` 并集 + 用户手动添加 − 用户手动删除。
个股板块由 AI 推断（东方财富行业/概念板块的叫法），每只股票只推断一次。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sector import OVERRIDE_ADD, OVERRIDE_REMOVE, FocusSectorOverride, StockSector
from app.models.watchlist_item import WatchlistItem
from app.services.llm_providers import LLMProviderError

logger = logging.getLogger(__name__)

MAX_SECTOR_NAME_LENGTH = 32
MAX_SECTORS_PER_STOCK = 3

SECTOR_SYSTEM_PROMPT = (
    "你是 A 股行业分析助手。给定一只股票，判断它最核心的 1～3 个所属板块，"
    "板块名称使用东方财富行业板块或概念板块的常用叫法（如：半导体、消费电子、AI芯片、光模块、白酒、银行）。"
    '只返回 JSON：{"sectors": ["板块1", "板块2"]}，按相关度从高到低排列。'
)


@dataclass
class FocusSector:
    name: str
    source: str  # ai | user
    symbols: list[str] = field(default_factory=list)


def normalize_sector_name(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    text = name.strip()
    if not text or len(text) > MAX_SECTOR_NAME_LENGTH:
        return None
    return text


def list_focus_sectors(session: Session) -> list[FocusSector]:
    active_symbols = [
        symbol.upper()
        for symbol in session.scalars(select(WatchlistItem.symbol).where(WatchlistItem.is_active.is_(True)))
    ]
    overrides = {row.sector: row.action for row in session.scalars(select(FocusSectorOverride))}

    sectors: dict[str, FocusSector] = {}
    if active_symbols:
        rows = session.scalars(
            select(StockSector).where(StockSector.symbol.in_(active_symbols)).order_by(StockSector.id)
        )
        order = {symbol: index for index, symbol in enumerate(active_symbols)}
        for row in sorted(rows, key=lambda r: (order.get(r.symbol.upper(), 0), r.id)):
            if overrides.get(row.sector) == OVERRIDE_REMOVE:
                continue
            sector = sectors.setdefault(row.sector, FocusSector(name=row.sector, source="ai"))
            if row.symbol.upper() not in sector.symbols:
                sector.symbols.append(row.symbol.upper())

    for override in session.scalars(select(FocusSectorOverride).order_by(FocusSectorOverride.id)):
        if override.action == OVERRIDE_ADD and override.sector not in sectors:
            sectors[override.sector] = FocusSector(name=override.sector, source="user")
    return list(sectors.values())


def _set_override(session: Session, name: object, action: str) -> str:
    sector = normalize_sector_name(name)
    if sector is None:
        raise ValueError("板块名称不能为空，且不超过 32 个字")
    row = session.scalar(select(FocusSectorOverride).where(FocusSectorOverride.sector == sector))
    if row is None:
        session.add(FocusSectorOverride(sector=sector, action=action))
    else:
        row.action = action
    session.flush()
    return sector


def add_focus_sector(session: Session, name: object) -> str:
    return _set_override(session, name, OVERRIDE_ADD)


def remove_focus_sector(session: Session, name: object) -> str:
    return _set_override(session, name, OVERRIDE_REMOVE)


class SectorInferenceService:
    def __init__(self, session: Session, provider) -> None:
        self.session = session
        self.provider = provider
        self.failed_symbols: list[str] = []

    def _stocks_without_sectors(self, limit: int, exclude: set[str]) -> list[WatchlistItem]:
        known = set(self.session.scalars(select(StockSector.symbol).distinct()))
        items = self.session.scalars(
            select(WatchlistItem).where(WatchlistItem.is_active.is_(True)).order_by(WatchlistItem.id)
        )
        return [item for item in items if item.symbol.upper() not in known and item.symbol.upper() not in exclude][
            :limit
        ]

    def infer_missing(self, *, limit: int = 1, exclude: set[str] | frozenset[str] = frozenset()) -> int:
        """给还没有板块的自选股各推断一次，返回成功推断的股票数。

        失败（LLM 报错或没给出可用板块）的代码记在 ``failed_symbols``，由调用方决定是否
        放进 ``exclude`` 不再重试，避免一只股票反复失败、每个周期都花钱还挡住后面的股票。
        """
        from app.services.ai.llm_json import complete_json

        self.failed_symbols = []
        inferred = 0
        for item in self._stocks_without_sectors(limit, {symbol.upper() for symbol in exclude}):
            symbol = item.symbol.upper()
            try:
                payload = complete_json(
                    self.provider,
                    system=SECTOR_SYSTEM_PROMPT,
                    user=f"股票：{item.display_name}（{symbol}，市场 {item.market}）",
                    operation_type="sector_infer",
                )
            except LLMProviderError as exc:
                logger.warning("sector inference failed for %s: %s", symbol, exc)
                self.failed_symbols.append(symbol)
                continue
            raw = payload.get("sectors") if isinstance(payload, dict) else None
            names: list[str] = []
            for value in raw if isinstance(raw, list) else []:
                name = normalize_sector_name(value)
                if name and name not in names:
                    names.append(name)
            if not names:
                self.failed_symbols.append(symbol)
                continue
            for name in names[:MAX_SECTORS_PER_STOCK]:
                self.session.add(StockSector(symbol=symbol, sector=name, source="ai"))
            self.session.flush()
            inferred += 1
        return inferred
