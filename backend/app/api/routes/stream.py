from fastapi import APIRouter

from app.schemas.stream import StreamStatusResponse

router = APIRouter()


@router.get("/status", response_model=StreamStatusResponse)
def stream_status() -> StreamStatusResponse:
    return StreamStatusResponse(mode="sse", status="planned")
