from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.alert import Alert


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_if_absent(
        self,
        *,
        kind: str,
        severity: str,
        symbol: str | None,
        title: str,
        body: str,
        payload: dict[str, Any],
        dedupe_key: str,
        overnight: bool,
        visible_at: datetime,
        created_at: datetime,
    ) -> Alert | None:
        """按 ``dedupe_key`` 幂等写入；已存在返回 None。

        先查后插 + 唯一约束兜底：并发写同一键时，后到者在 savepoint 内撞唯一约束后回滚该
        savepoint，不影响调用方事务里的其他写入。
        """
        if self.session.scalar(select(Alert.id).where(Alert.dedupe_key == dedupe_key)) is not None:
            return None
        alert = Alert(
            kind=kind,
            severity=severity,
            symbol=symbol,
            title=title[:255],
            body=body,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            dedupe_key=dedupe_key,
            overnight=overnight,
            visible_at=visible_at,
            created_at=created_at,
        )
        try:
            with self.session.begin_nested():
                self.session.add(alert)
                self.session.flush()
        except IntegrityError:
            return None
        return alert

    def list_visible(self, *, now: datetime, unread_only: bool, limit: int) -> list[Alert]:
        stmt = select(Alert).where(Alert.visible_at <= now)
        if unread_only:
            stmt = stmt.where(Alert.read_at.is_(None))
        stmt = stmt.order_by(Alert.visible_at.desc(), Alert.id.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def unread_count(self, *, now: datetime) -> int:
        stmt = select(func.count(Alert.id)).where(Alert.visible_at <= now, Alert.read_at.is_(None))
        return int(self.session.scalar(stmt) or 0)

    def mark_read(self, alert_id: int, *, now: datetime) -> bool:
        alert = self.session.get(Alert, alert_id)
        if alert is None:
            return False
        if alert.read_at is None:
            alert.read_at = now
        return True

    def mark_all_read(self, *, now: datetime) -> int:
        result = self.session.execute(
            update(Alert)
            .where(Alert.visible_at <= now, Alert.read_at.is_(None))
            .values(read_at=now)
        )
        return int(result.rowcount or 0)
