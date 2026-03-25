from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source_health import SourceHealth


class SourceHealthRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[SourceHealth]:
        stmt = select(SourceHealth).order_by(SourceHealth.source_name.asc(), SourceHealth.market.asc())
        return list(self.session.scalars(stmt))

    def get_or_create(self, *, source_name: str, source_type: str, market: str) -> SourceHealth:
        stmt = select(SourceHealth).where(
            SourceHealth.source_name == source_name,
            SourceHealth.market == market,
        )
        instance = self.session.scalar(stmt)
        if instance is not None:
            return instance

        instance = SourceHealth(
            source_name=source_name,
            market=market,
            source_type=source_type,
            consecutive_failures=0,
            total_fetches=0,
            total_failures=0,
            is_disabled=False,
        )
        self.session.add(instance)
        self.session.flush()
        return instance
