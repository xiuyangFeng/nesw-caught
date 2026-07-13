from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.digest import DigestLatestView, DigestSectionView, DigestView
from app.services.digest_service import Digest, generate_digest, get_latest_digest

router = APIRouter()


def _to_view(digest: Digest) -> DigestView:
    return DigestView(
        title=digest.title,
        market_scope=digest.market_scope,
        generated_at=digest.generated_at,
        generated_by=digest.generated_by,
        model_name=digest.model_name,
        sections=[DigestSectionView(title=s.title, body=s.body) for s in digest.sections],
    )


@router.get("/latest", response_model=DigestLatestView)
def get_latest(session: Session = Depends(get_db_session)) -> DigestLatestView:
    digest = get_latest_digest()
    if digest is None:
        return DigestLatestView(available=False, digest=None)
    return DigestLatestView(available=True, digest=_to_view(digest))


@router.post("/generate", response_model=DigestView)
def generate(
    market_scope: str = Query(default="all"),
    session: Session = Depends(get_db_session),
) -> DigestView:
    digest = generate_digest(market_scope, session)
    return _to_view(digest)
