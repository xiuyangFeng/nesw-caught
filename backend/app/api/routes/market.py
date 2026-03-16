from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.market_repository import MarketRepository
from app.schemas.market import PriceSnapshotView

router = APIRouter()


@router.get("/snapshots", response_model=list[PriceSnapshotView])
def list_market_snapshots(session: Session = Depends(get_db_session)) -> list[PriceSnapshotView]:
    repository = MarketRepository(session)
    snapshots = repository.list_latest()
    response: list[PriceSnapshotView] = []
    for snapshot in snapshots:
        is_abnormal = abs(snapshot.change_percent or 0.0) >= 3
        response.append(
            PriceSnapshotView(
                symbol=snapshot.symbol,
                market=snapshot.market,
                display_name=None,
                price=snapshot.price,
                change_amount=snapshot.change_amount,
                change_percent=snapshot.change_percent,
                volume=snapshot.volume,
                is_abnormal=is_abnormal,
                abnormal_reason="price_move" if is_abnormal else None,
                fetched_at=snapshot.fetched_at,
            )
        )
    return response
