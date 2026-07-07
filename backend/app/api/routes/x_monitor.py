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
    XRadarResponse,
    XRefreshResponse,
)
from app.services.x_monitor import (
    XAccountAlreadyExistsError,
    XAccountNotFoundError,
    XMonitorDisabledError,
    XMonitorService,
)

router = APIRouter()

# Single place mapping domain errors to HTTP status codes. Unmatched
# ValueError (e.g. malformed accounts file) falls back to 400.
_ERROR_STATUS_CODES: tuple[tuple[type[ValueError], int], ...] = (
    (XMonitorDisabledError, 503),
    (XAccountNotFoundError, 404),
    (XAccountAlreadyExistsError, 409),
)


def _http_error(exc: ValueError) -> HTTPException:
    for error_type, status_code in _ERROR_STATUS_CODES:
        if isinstance(exc, error_type):
            return HTTPException(status_code=status_code, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _service(session: Session) -> XMonitorService:
    return XMonitorService(session)


def _enabled(service: XMonitorService) -> None:
    try:
        service.ensure_enabled()
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/accounts", response_model=list[XAccountView])
def list_accounts(session: Session = Depends(get_db_session)) -> list[XAccountView]:
    service = _service(session)
    _enabled(service)
    return [XAccountView.model_validate(item, from_attributes=True) for item in service.list_accounts()]


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
        raise _http_error(exc) from exc
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
        raise _http_error(exc) from exc
    return XAccountView.model_validate(account, from_attributes=True)


@router.delete("/accounts/{handle}", status_code=204)
def delete_account(handle: str, session: Session = Depends(get_db_session)) -> Response:
    service = _service(session)
    _enabled(service)
    try:
        service.delete_account(handle)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=204)


@router.post("/accounts/import", response_model=XAccountsImportResult)
def import_accounts(session: Session = Depends(get_db_session)) -> XAccountsImportResult:
    service = _service(session)
    _enabled(service)
    try:
        result = service.import_accounts_from_file()
    except ValueError as exc:
        raise _http_error(exc) from exc
    return XAccountsImportResult.model_validate(result, from_attributes=True)


@router.post("/accounts/export", response_model=XAccountsExportResult)
def export_accounts(session: Session = Depends(get_db_session)) -> XAccountsExportResult:
    service = _service(session)
    _enabled(service)
    try:
        result = service.export_accounts_to_file()
    except ValueError as exc:
        raise _http_error(exc) from exc
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
    return service.list_posts(
        account_handle=account_handle,
        symbol=symbol,
        market=market,
        query=q,
        limit=limit,
    )


@router.get("/search", response_model=list[XPostSummaryView])
def search_posts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[XPostSummaryView]:
    service = _service(session)
    _enabled(service)
    return service.search_posts(query=q, limit=limit)


@router.get("/radar", response_model=XRadarResponse)
def get_radar(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> XRadarResponse:
    service = _service(session)
    _enabled(service)
    return service.get_radar(limit=limit)


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
