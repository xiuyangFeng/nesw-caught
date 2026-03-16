from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.x_source_health import XSourceHealth


class XSourceHealthRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, provider_name: str) -> XSourceHealth:
        stmt = select(XSourceHealth).where(XSourceHealth.provider_name == provider_name)
        instance = self.session.scalar(stmt)
        if instance is not None:
            return instance

        instance = XSourceHealth(
            provider_name=provider_name,
            consecutive_failures=0,
            total_fetches=0,
            total_failures=0,
        )
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, provider_name: str) -> XSourceHealth | None:
        stmt = select(XSourceHealth).where(XSourceHealth.provider_name == provider_name)
        return self.session.scalar(stmt)
