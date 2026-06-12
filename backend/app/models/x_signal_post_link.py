from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XSignalPostLink(Base):
    __tablename__ = "x_signal_post_link"
    __table_args__ = (UniqueConstraint("signal_id", "post_id", name="uq_x_signal_post_link_signal_post"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("x_signal.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("x_post.id", ondelete="CASCADE"), index=True)
    evidence_rank: Mapped[int] = mapped_column(default=0)
    match_reason: Mapped[str | None] = mapped_column(String(64), default=None)
