from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.x_account import XAccount


class XAccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[XAccount]:
        stmt = select(XAccount).order_by(XAccount.priority.desc(), XAccount.handle.asc())
        return list(self.session.scalars(stmt))

    def list_active(self) -> list[XAccount]:
        stmt = (
            select(XAccount)
            .where(XAccount.is_active.is_(True))
            .order_by(XAccount.priority.desc(), XAccount.handle.asc())
        )
        return list(self.session.scalars(stmt))

    def get_by_handle(self, handle: str) -> XAccount | None:
        stmt = select(XAccount).where(XAccount.handle == handle.lstrip("@"))
        return self.session.scalar(stmt)

    def upsert_many(self, accounts: list[dict[str, object]]) -> list[XAccount]:
        instances: list[XAccount] = []
        for item in accounts:
            handle = str(item["handle"]).lstrip("@")
            instance = self.get_by_handle(handle)
            if instance is None:
                instance = XAccount(
                    handle=handle,
                    display_name=str(item.get("display_name") or handle),
                    market_focus=str(item.get("market_focus")) if item.get("market_focus") else None,
                    is_active=bool(item.get("is_active", True)),
                    priority=int(item.get("priority", 0)),
                    notes=str(item.get("notes")) if item.get("notes") else None,
                )
                self.session.add(instance)
            else:
                instance.display_name = str(item.get("display_name") or instance.display_name)
                instance.market_focus = (
                    str(item.get("market_focus")) if item.get("market_focus") else instance.market_focus
                )
                instance.is_active = bool(item.get("is_active", instance.is_active))
                instance.priority = int(item.get("priority", instance.priority))
                instance.notes = str(item.get("notes")) if item.get("notes") else instance.notes
            instances.append(instance)

        self.session.flush()
        return instances
