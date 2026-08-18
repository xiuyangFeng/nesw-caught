"""快循环雷达：新闻入库后更新候选，不把 D 级传闻直接 qualified。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.quant import RadarEvent
from app.services.quant.events import classify_event, propose_state

__all__ = ["ingest_news", "list_recent", "propose_state"]


def ingest_news(session: Session, news: NewsItem, mentions: list[NewsStockMention]) -> list[RadarEvent]:
    classified = classify_event(
        title=news.title,
        source_name=news.source_name,
        source_url=news.source_url or news.canonical_url,
        summary=news.summary,
    )
    quality = {"A": 1.0, "B": 0.8, "C": 0.55, "D": 0.2}[classified.evidence_grade]
    state = propose_state(
        evidence_grade=classified.evidence_grade,
        novelty=0.8,
        materiality=0.8 if classified.event_type != "general" else 0.4,
        evidence_quality=quality,
        reaction_gap=0.7,
    )
    written: list[RadarEvent] = []
    for mention in mentions:
        existing = session.scalar(
            select(RadarEvent).where(
                RadarEvent.news_id == news.id,
                RadarEvent.symbol == mention.symbol,
            )
        )
        if existing is not None:
            continue
        row = RadarEvent(
            symbol=mention.symbol,
            news_id=news.id,
            event_type=classified.event_type,
            evidence_grade=classified.evidence_grade,
            state=state.value,
            reason_code=f"grade_{classified.evidence_grade.lower()}_{classified.event_type}",
            novelty=0.8,
            materiality=0.8 if classified.event_type != "general" else 0.4,
            score=0.8 * quality,
            title=news.title,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        written.append(row)
    return written


def list_recent(session: Session, *, limit: int = 40) -> list[RadarEvent]:
    return list(
        session.scalars(select(RadarEvent).order_by(RadarEvent.created_at.desc()).limit(limit))
    )
