from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XAccount(Base):
    __tablename__ = "x_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    market_focus: Mapped[str | None] = mapped_column(String(16), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    priority: Mapped[int] = mapped_column(Integer(), default=0)
    tier: Mapped[str] = mapped_column(String(16), default="watch")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    notes: Mapped[str | None] = mapped_column(Text(), default=None)
