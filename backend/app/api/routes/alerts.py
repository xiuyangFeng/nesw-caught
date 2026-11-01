from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.alert import Alert
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertReadAllView, AlertUnreadCountView, AlertView

router = APIRouter()


def _now() -> datetime:
    return datetime.now(UTC)


def to_alert_view(alert: Alert) -> AlertView:
    try:
        payload = json.loads(alert.payload_json or "{}")
    except ValueError:
        payload = {}
    return AlertView(
        id=alert.id,
        kind=alert.kind,
        severity=alert.severity,
        symbol=alert.symbol,
        title=alert.title,
        body=alert.body,
        payload=payload if isinstance(payload, dict) else {},
        overnight=alert.overnight,
        created_at=alert.created_at,
        visible_at=alert.visible_at,
        read_at=alert.read_at,
    )


@router.get("", response_model=list[AlertView])
def list_alerts(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> list[AlertView]:
    """当前可见的站内提醒（隔夜提醒在次日早上之前不出现），新的在前。"""
    alerts = AlertRepository(session).list_visible(now=_now(), unread_only=unread_only, limit=limit)
    return [to_alert_view(alert) for alert in alerts]


@router.get("/unread-count", response_model=AlertUnreadCountView)
def get_unread_count(session: Session = Depends(get_db_session)) -> AlertUnreadCountView:
    return AlertUnreadCountView(unread=AlertRepository(session).unread_count(now=_now()))


@router.post("/read-all", response_model=AlertReadAllView)
def mark_all_read(session: Session = Depends(get_db_session)) -> AlertReadAllView:
    updated = AlertRepository(session).mark_all_read(now=_now())
    session.commit()
    return AlertReadAllView(updated=updated)


@router.post("/{alert_id}/read", response_model=AlertView)
def mark_read(alert_id: int, session: Session = Depends(get_db_session)) -> AlertView:
    repo = AlertRepository(session)
    if not repo.mark_read(alert_id, now=_now()):
        raise HTTPException(status_code=404, detail="alert not found")
    session.commit()
    alert = session.get(Alert, alert_id)
    assert alert is not None
    return to_alert_view(alert)
