from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm_classification_cache import LLMClassificationCache


class LLMClassificationCacheRepository:
    """分类结果缓存读写。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_hash(self, content_hash: str) -> LLMClassificationCache | None:
        stmt = select(LLMClassificationCache).where(
            LLMClassificationCache.content_hash == content_hash
        )
        return self.session.scalar(stmt)

    def upsert(
        self,
        *,
        content_hash: str,
        result_json: str,
        model_name: str | None = None,
    ) -> LLMClassificationCache:
        entry = self.get_by_hash(content_hash)
        if entry is None:
            entry = LLMClassificationCache(
                content_hash=content_hash,
                result_json=result_json,
                model_name=model_name,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(entry)
        else:
            entry.result_json = result_json
            entry.model_name = model_name
        self.session.flush()
        return entry
