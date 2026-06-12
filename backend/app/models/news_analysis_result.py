from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsAnalysisResult(Base):
    __tablename__ = "news_analysis_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_item.id", ondelete="CASCADE"), unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(64), index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    analysis_status: Mapped[str] = mapped_column(String(32), default="success")
    top_pick_symbol: Mapped[str | None] = mapped_column(String(32), default=None)
    top_pick_market: Mapped[str | None] = mapped_column(String(16), default=None)
    top_pick_company_name: Mapped[str | None] = mapped_column(String(255), default=None)
    top_pick_confidence: Mapped[str | None] = mapped_column(String(32), default=None)
    top_pick_reason: Mapped[str | None] = mapped_column(Text(), default=None)
    summary: Mapped[str | None] = mapped_column(Text(), default=None)
    risk_notes: Mapped[str | None] = mapped_column(Text(), default=None)
    sentiment: Mapped[str | None] = mapped_column(String(32), default=None)
    context_limitations: Mapped[str | None] = mapped_column(Text(), default=None)
    raw_response_json: Mapped[str | None] = mapped_column(Text(), default=None)
    analysis_error: Mapped[str | None] = mapped_column(Text(), default=None)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
