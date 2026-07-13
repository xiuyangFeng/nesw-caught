from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMClassificationCache(Base):
    """相同内容分类结果缓存。

    以归一化内容的 sha256 作为唯一键，命中后直接复用历史分类结果，
    避免对相同内容重复调用 LLM，从而节省 token 花费。
    """

    __tablename__ = "llm_classification_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 归一化内容的 sha256 十六进制摘要（唯一）。
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 缓存的分类结果 JSON 字符串（LLM 返回的原始 content）。
    result_json: Mapped[str] = mapped_column(Text())
    # 生成该缓存时所用的模型名称，仅供审计。
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
