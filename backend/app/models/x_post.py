from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XPost(Base):
    __tablename__ = "x_post"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("x_account.id", ondelete="CASCADE"), index=True)
    external_post_id: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    canonical_url: Mapped[str | None] = mapped_column(String(500), unique=True, default=None)
    content_text: Mapped[str] = mapped_column(Text())
    market: Mapped[str] = mapped_column(String(16), default="us", index=True)
    sentiment_label: Mapped[str] = mapped_column(String(16), default="unknown")
    relevance_score: Mapped[float | None] = mapped_column(Float(), default=None)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text(), default=None)
    dedupe_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
