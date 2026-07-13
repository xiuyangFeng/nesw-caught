from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price_snapshot import PriceSnapshot


class MarketRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_latest(self) -> list[PriceSnapshot]:
        stmt = select(PriceSnapshot).order_by(PriceSnapshot.fetched_at.desc())
        return list(self.session.scalars(stmt))

    def list_latest_by_symbols(self, symbols: list[str]) -> dict[str, PriceSnapshot]:
        if not symbols:
            return {}
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol.in_(symbols))
            .order_by(PriceSnapshot.symbol, PriceSnapshot.fetched_at.desc())
        )
        latest: dict[str, PriceSnapshot] = {}
        for snapshot in self.session.scalars(stmt):
            if snapshot.symbol not in latest:
                latest[snapshot.symbol] = snapshot
        return latest

    def list_snapshots_by_symbols(self, symbols: list[str]) -> dict[str, list[PriceSnapshot]]:
        """按 symbol 批量取全部历史快照，按 fetched_at 升序分组（只读，供回测取基准价/前视价）。"""
        if not symbols:
            return {}
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol.in_(symbols))
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
