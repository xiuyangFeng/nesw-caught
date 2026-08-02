from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_index_config import MarketIndexConfig

# update 允许写入的字段白名单：symbol 与 market 不允许改
# （改了就当删除+新增，语义更清晰），其余键直接忽略。
_MUTABLE_FIELDS = ("display_name", "kind", "sort_order", "enabled")


class MarketOverviewRepository:
    """market_index_config 配置表 CRUD（市场总览）。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _sorted_stmt(self):
        return select(MarketIndexConfig).order_by(
            MarketIndexConfig.market,
            MarketIndexConfig.sort_order,
            MarketIndexConfig.id,
        )

    def list_all(self) -> list[MarketIndexConfig]:
        """全部配置（含 disabled），按 (market, sort_order) 排序。"""
        return list(self.session.scalars(self._sorted_stmt()))

    def list_enabled(self) -> list[MarketIndexConfig]:
        """仅 enabled 条目，按 (market, sort_order) 排序（overview 轮询/展示用）。"""
        stmt = self._sorted_stmt().where(MarketIndexConfig.enabled.is_(True))
        return list(self.session.scalars(stmt))

    def get(self, config_id: int) -> MarketIndexConfig | None:
        return self.session.get(MarketIndexConfig, config_id)

    def create(
        self,
        *,
        symbol: str,
        market: str,
        display_name: str,
        kind: str = "index",
        sort_order: int = 0,
        enabled: bool = True,
    ) -> MarketIndexConfig:
        item = MarketIndexConfig(
            symbol=symbol,
            market=market,
            display_name=display_name,
            kind=kind,
            sort_order=sort_order,
            enabled=enabled,
        )
        self.session.add(item)
        self.session.flush()
        self.session.refresh(item)
        return item

    def update(self, config_id: int, updates: dict) -> MarketIndexConfig | None:
        """按白名单更新可变字段；找不到 id 返回 None。

        upsert 语义之外的字段（symbol/market/未知键）一律忽略，保证
        symbol 与 market 在 repository 层没有修改入口。
        """
        item = self.get(config_id)
        if item is None:
            return None
        for field in _MUTABLE_FIELDS:
            if field in updates:
                setattr(item, field, updates[field])
        self.session.flush()
        self.session.refresh(item)
        return item

    def delete(self, config_id: int) -> bool:
        """物理删除（单用户本地应用，不做回收站）。"""
        item = self.get(config_id)
        if item is None:
            return False
        self.session.delete(item)
        self.session.flush()
        return True
