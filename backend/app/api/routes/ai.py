"""AI 漏斗接口（聚焦改造 P3）：新闻 AI 结论与用户修正、个股影响、关注板块、漏斗状态。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.news_ai import NewsAiAnalysis, NewsAiScreen, NewsImpact
from app.models.news_item import NewsItem
from app.schemas.ai import (
    AiFunnelStatusView,
    FocusSectorCreate,
    FocusSectorView,
    ImpactCorrectionRequest,
    NewsAiAnalysisView,
    NewsAiScreenView,
    NewsAiView,
    NewsImpactView,
    StockImpactView,
)
from app.services.ai.context import load_portfolio_context
from app.services.ai.impact import replace_impacts_by_user
from app.services.ai.sectors import add_focus_sector, list_focus_sectors, remove_focus_sector
from app.services.ai.status import funnel_status

router = APIRouter()


def _impact_view(row: NewsImpact) -> NewsImpactView:
    return NewsImpactView(
        id=row.id,
        target_type=row.target_type,
        code=row.target_code,
        name=row.target_name,
        direction=row.direction,
        strength=row.strength,
        rationale=row.rationale,
        source=row.source,
    )


def _news_ai_view(session: Session, news_id: int) -> NewsAiView:
    screen = session.scalar(select(NewsAiScreen).where(NewsAiScreen.news_id == news_id))
    analysis = session.scalar(select(NewsAiAnalysis).where(NewsAiAnalysis.news_id == news_id))
    impacts = session.scalars(select(NewsImpact).where(NewsImpact.news_id == news_id).order_by(NewsImpact.id)).all()
    return NewsAiView(
        news_id=news_id,
        screen=NewsAiScreenView.model_validate(screen, from_attributes=True) if screen else None,
        analysis=NewsAiAnalysisView.model_validate(analysis, from_attributes=True) if analysis else None,
        impacts=[_impact_view(row) for row in impacts],
    )


def _require_news(session: Session, news_id: int) -> NewsItem:
    item = session.get(NewsItem, news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="news not found")
    return item


@router.get("/news/{news_id}/ai", response_model=NewsAiView)
def get_news_ai(news_id: int, session: Session = Depends(get_db_session)) -> NewsAiView:
    """新闻的 AI 粗筛、精读结论与影响列表；尚未经过 AI 时各项为空。"""
    _require_news(session, news_id)
    return _news_ai_view(session, news_id)


@router.put("/news/{news_id}/impacts", response_model=NewsAiView)
def correct_news_impacts(
    news_id: int, payload: ImpactCorrectionRequest, session: Session = Depends(get_db_session)
) -> NewsAiView:
    """用户修正影响列表（整表替换）；修正会作为后续 AI 判断的示例。"""
    _require_news(session, news_id)
    try:
        replace_impacts_by_user(
            session,
            news_id,
            [item.model_dump() for item in payload.impacts],
            note=payload.note,
            context=load_portfolio_context(session),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return _news_ai_view(session, news_id)


@router.get("/watchlist/{symbol}/impacts", response_model=list[StockImpactView])
def list_stock_impacts(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[StockImpactView]:
    """某只股票最近的 AI（或用户修正）影响判断，新的在前。"""
    rows = session.execute(
        select(NewsImpact, NewsItem, NewsAiScreen.title_zh, NewsAiAnalysis.view)
        .join(NewsItem, NewsItem.id == NewsImpact.news_id)
        .outerjoin(NewsAiScreen, NewsAiScreen.news_id == NewsImpact.news_id)
        .outerjoin(NewsAiAnalysis, NewsAiAnalysis.news_id == NewsImpact.news_id)
        .where(NewsImpact.target_type == "stock", NewsImpact.target_code == symbol.upper())
        .order_by(NewsItem.effective_at.desc(), NewsImpact.id.desc())
        .limit(limit)
    ).all()
    return [
        StockImpactView(
            news_id=item.id,
            news_title=item.title,
            title_zh=title_zh,
            published_at=item.published_at or item.fetched_at,
            direction=impact.direction,
            strength=impact.strength,
            rationale=impact.rationale,
            source=impact.source,
            view=view,
        )
        for impact, item, title_zh, view in rows
    ]


@router.get("/focus-sectors", response_model=list[FocusSectorView])
def get_focus_sectors(session: Session = Depends(get_db_session)) -> list[FocusSectorView]:
    """关注板块：自选股的 AI 推断板块 + 手动添加 − 手动删除。"""
    return [FocusSectorView(name=s.name, source=s.source, symbols=s.symbols) for s in list_focus_sectors(session)]


@router.post("/focus-sectors", response_model=list[FocusSectorView], status_code=status.HTTP_201_CREATED)
def create_focus_sector(payload: FocusSectorCreate, session: Session = Depends(get_db_session)) -> list[FocusSectorView]:
    try:
        add_focus_sector(session, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return get_focus_sectors(session)


@router.delete("/focus-sectors/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_focus_sector(name: str, session: Session = Depends(get_db_session)) -> Response:
    try:
        remove_focus_sector(session, name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ai/funnel/status", response_model=AiFunnelStatusView)
def get_funnel_status(session: Session = Depends(get_db_session)) -> AiFunnelStatusView:
    """AI 漏斗是否在线、今日处理量与费用、预算、最近错误。"""
    return AiFunnelStatusView.model_validate(funnel_status(session))
