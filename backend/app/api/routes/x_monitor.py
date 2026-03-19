from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.x_monitor import XAccountView, XPostSummaryView, XRefreshResponse
from app.services.x_monitor import XMonitorService

router = APIRouter()


def _service(session: Session) -> XMonitorService:
    return XMonitorService(session)


def _enabled(service: XMonitorService) -> None:
    try:
        service.ensure_enabled()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/accounts", response_model=list[XAccountView])
def list_accounts(session: Session = Depends(get_db_session)) -> list[XAccountView]:
    service = _service(session)
    _enabled(service)
    service.sync_accounts_from_file()
    return [XAccountView.model_validate(item, from_attributes=True) for item in service.accounts.list_all()]


@router.get("/posts", response_model=list[XPostSummaryView])
def list_posts(
    account_handle: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    market: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> list[XPostSummaryView]:
    service = _service(session)
    _enabled(service)
    rows = service.posts.list_posts(
        account_handle=account_handle,
        symbol=symbol,
        market=market,
        query=q,
        limit=limit,
    )
    return [
        XPostSummaryView(
            id=post.id,
            account_handle=account.handle,
            account_display_name=account.display_name,
            content_text=post.content_text,
            canonical_url=post.canonical_url,
            market=post.market,
            sentiment_label=post.sentiment_label,
            relevance_score=post.relevance_score,
            posted_at=post.posted_at,
            captured_at=post.captured_at,
            symbols=symbols,
        )
        for post, account, symbols in rows
    ]


@router.get("/search", response_model=list[XPostSummaryView])
def search_posts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[XPostSummaryView]:
    service = _service(session)
    _enabled(service)
    return service.search_posts(query=q, limit=limit)


@router.post("/refresh", response_model=XRefreshResponse)
def refresh_posts(session: Session = Depends(get_db_session)) -> XRefreshResponse:
    service = _service(session)
    _enabled(service)
    summary = service.refresh()
    return XRefreshResponse(
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        fetched_count=summary.fetched_count,
        inserted_count=summary.inserted_count,
        error=summary.error,
        latency_ms=summary.latency_ms,
        skipped=summary.skipped,
        skip_reason=summary.skip_reason,
        next_refresh_at=summary.next_refresh_at,
    )
