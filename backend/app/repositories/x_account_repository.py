from sqlalchemy import case, select
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

    def list_refresh_targets(self) -> list[XAccount]:
        tier_rank = case(
            (XAccount.tier == "core", 0),
            (XAccount.tier == "watch", 1),
            else_=2,
        )
        stmt = (
            select(XAccount)
            .where(XAccount.is_active.is_(True), XAccount.tier != "muted")
            .order_by(tier_rank.asc(), XAccount.priority.desc(), XAccount.handle.asc())
        )
        return list(self.session.scalars(stmt))

    def get_by_handle(self, handle: str) -> XAccount | None:
        stmt = select(XAccount).where(XAccount.handle == handle.lstrip("@"))
        return self.session.scalar(stmt)

    def create(self, payload: dict[str, object]) -> XAccount:
        instance = XAccount(
            handle=str(payload["handle"]).lstrip("@"),
            display_name=str(payload.get("display_name") or payload["handle"]).strip(),
            market_focus=str(payload.get("market_focus")) if payload.get("market_focus") else None,
            is_active=bool(payload.get("is_active", True)),
            priority=int(payload.get("priority", 0)),
            tier=str(payload.get("tier") or "watch"),
            source=str(payload.get("source") or "manual"),
            notes=str(payload.get("notes")) if payload.get("notes") else None,
        )
        self.session.add(instance)
        self.session.flush()
        return instance

    def update(self, instance: XAccount, payload: dict[str, object]) -> XAccount:
        if "display_name" in payload and payload["display_name"] is not None:
            instance.display_name = str(payload["display_name"]).strip()
        if "market_focus" in payload:
            instance.market_focus = str(payload["market_focus"]) if payload["market_focus"] else None
        if "is_active" in payload and payload["is_active"] is not None:
            instance.is_active = bool(payload["is_active"])
        if "priority" in payload and payload["priority"] is not None:
            instance.priority = int(payload["priority"])
        if "tier" in payload and payload["tier"] is not None:
            instance.tier = str(payload["tier"])
        if "source" in payload and payload["source"] is not None:
            instance.source = str(payload["source"])
        if "notes" in payload:
            instance.notes = str(payload["notes"]) if payload["notes"] else None
        self.session.flush()
        return instance

    def delete(self, instance: XAccount) -> None:
        self.session.delete(instance)
        self.session.flush()

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
                    tier=str(item.get("tier") or "watch"),
                    source=str(item.get("source") or "manual"),
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
                instance.tier = str(item.get("tier") or instance.tier)
                instance.source = str(item.get("source") or instance.source)
                instance.notes = str(item.get("notes")) if item.get("notes") else instance.notes
            instances.append(instance)

        self.session.flush()
        return instances
