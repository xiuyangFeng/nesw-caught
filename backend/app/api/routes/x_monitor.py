from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.x_monitor import (
    XAccountCreateRequest,
    XAccountUpdateRequest,
    XAccountView,
    XAccountsExportResult,
    XAccountsImportResult,
    XPostSummaryView,
    XRefreshResponse,
)
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
    return [XAccountView.model_validate(item, from_attributes=True) for item in service.accounts.list_all()]


@router.post("/accounts", response_model=XAccountView)
def create_account(
    payload: XAccountCreateRequest,
    session: Session = Depends(get_db_session),
) -> XAccountView:
    service = _service(session)
    _enabled(service)
    try:
        account = service.create_account(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return XAccountView.model_validate(account, from_attributes=True)


@router.patch("/accounts/{handle}", response_model=XAccountView)
def update_account(
    handle: str,
    payload: XAccountUpdateRequest,
    session: Session = Depends(get_db_session),
) -> XAccountView:
    service = _service(session)
    _enabled(service)
    try:
        account = service.update_account(handle, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return XAccountView.model_validate(account, from_attributes=True)


@router.delete("/accounts/{handle}", status_code=204)
def delete_account(handle: str, session: Session = Depends(get_db_session)) -> Response:
    service = _service(session)
    _enabled(service)
    try:
        service.delete_account(handle)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/accounts/import", response_model=XAccountsImportResult)
def import_accounts(session: Session = Depends(get_db_session)) -> XAccountsImportResult:
    service = _service(session)
    _enabled(service)
    try:
        result = service.import_accounts_from_file()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return XAccountsImportResult.model_validate(result, from_attributes=True)


@router.post("/accounts/export", response_model=XAccountsExportResult)
def export_accounts(session: Session = Depends(get_db_session)) -> XAccountsExportResult:
    service = _service(session)
    _enabled(service)
    try:
        result = service.export_accounts_to_file()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return XAccountsExportResult.model_validate(result, from_attributes=True)


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
