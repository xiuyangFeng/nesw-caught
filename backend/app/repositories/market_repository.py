from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price_snapshot import PriceSnapshot


class MarketRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_latest(self) -> list[PriceSnapshot]:
        stmt = select(PriceSnapshot).order_by(PriceSnapshot.fetched_at.desc())
        return list(self.session.scalars(stmt))
