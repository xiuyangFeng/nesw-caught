from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.price_snapshot import PriceSnapshot


class MarketRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _latest_per_symbol_subquery(self, symbols: list[str] | None = None):
        stmt = select(
            PriceSnapshot.symbol.label("symbol"),
            func.max(PriceSnapshot.fetched_at).label("max_fetched_at"),
        )
        if symbols:
            stmt = stmt.where(PriceSnapshot.symbol.in_(symbols))
        return stmt.group_by(PriceSnapshot.symbol).subquery()

    def _fetch_latest_rows(self, symbols: list[str] | None = None) -> dict[str, PriceSnapshot]:
        """每 symbol 取最新一条快照（fetched_at 并列时取 id 最大者）。

        先 GROUP BY symbol + MAX(fetched_at) 聚合（走 ix_price_snapshot_symbol_fetched），
        再回表取整行；避免把每个 symbol 的全部历史物化到 Python。
        """
        latest_per_symbol = self._latest_per_symbol_subquery(symbols)
        stmt = select(PriceSnapshot).join(
            latest_per_symbol,
            and_(
                PriceSnapshot.symbol == latest_per_symbol.c.symbol,
                PriceSnapshot.fetched_at == latest_per_symbol.c.max_fetched_at,
            ),
        )
        if symbols:
            stmt = stmt.where(PriceSnapshot.symbol.in_(symbols))
        latest: dict[str, PriceSnapshot] = {}
        for snapshot in self.session.scalars(stmt):
            # fetched_at 并列时 join 会带回多行，只保留 id 最大的一条
            existing = latest.get(snapshot.symbol)
            if existing is None or snapshot.id > existing.id:
                latest[snapshot.symbol] = snapshot
        return latest

    def list_latest(self) -> list[PriceSnapshot]:
        """全市场每 symbol 最新一条，按 fetched_at 倒序（供 GET /market/snapshots）。"""
        latest = self._fetch_latest_rows()
        return sorted(latest.values(), key=lambda item: (item.fetched_at, item.id), reverse=True)

    def list_latest_by_symbols(self, symbols: list[str]) -> dict[str, PriceSnapshot]:
        if not symbols:
            return {}
        unique_symbols = list(dict.fromkeys(symbols))
        return self._fetch_latest_rows(unique_symbols)

    def list_snapshots_by_symbols(self, symbols: list[str]) -> dict[str, list[PriceSnapshot]]:
        """按 symbol 批量取全部历史快照，按 fetched_at 升序分组（只读，供回测取基准价/前视价）。

        回测语义本身需要完整历史，行数无法裁剪；仅做入参去重防护，
        查询走 ix_price_snapshot_symbol_fetched 索引。
        """
        if not symbols:
            return {}
        unique_symbols = list(dict.fromkeys(symbols))
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol.in_(unique_symbols))
            .order_by(PriceSnapshot.symbol, PriceSnapshot.fetched_at.asc())
        )
        grouped: dict[str, list[PriceSnapshot]] = {}
        for snapshot in self.session.scalars(stmt):
            grouped.setdefault(snapshot.symbol, []).append(snapshot)
        return grouped

    def save_snapshot(self, snapshot: PriceSnapshot) -> PriceSnapshot:
        self.session.add(snapshot)
        self.session.flush()
        self.session.refresh(snapshot)
        return snapshot
