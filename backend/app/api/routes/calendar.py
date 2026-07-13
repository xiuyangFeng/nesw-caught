from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.calendar import CalendarResponseView
from app.services.calendar_service import CalendarService

router = APIRouter()


def get_calendar_service() -> CalendarService:
    return CalendarService()


@router.get("", response_model=CalendarResponseView)
def list_upcoming_calendar(
    days: int = Query(30, ge=1, le=365, description="前视天数窗口"),
    session: Session = Depends(get_db_session),
) -> CalendarResponseView:
    service = get_calendar_service()
    return CalendarResponseView.model_validate(service.get_upcoming_events(session, days=days))


@router.get("/{symbol}", response_model=CalendarResponseView)
def get_symbol_calendar(
    symbol: str,
    days: int = Query(90, ge=1, le=365, description="前视天数窗口"),
    session: Session = Depends(get_db_session),
) -> CalendarResponseView:
    service = get_calendar_service()
    return CalendarResponseView.model_validate(service.get_symbol_calendar(symbol, session, days=days))
