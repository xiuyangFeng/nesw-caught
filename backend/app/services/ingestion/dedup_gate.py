from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.services.ingestion.types import DUPLICATE_WINDOW, SourceItem
from app.services.ingestion.utils import _normalize_datetime
from app.services.news_dedup import titles_look_duplicate


def _normalize_title_for_signature(title: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", title.lower())
    return " ".join(normalized.split())


def _build_duplicate_signature(item: SourceItem) -> str | None:
    # 签名不再包含小时桶:时间邻近性由 DuplicateGate.find_duplicate 的 ±DUPLICATE_WINDOW
    # 滑动窗口判定,避免 23:58 / 00:02 落在不同自然小时导致漏判。
    if _normalize_datetime(item.published_at) is None:
        return None

    normalized_title = _normalize_title_for_signature(item.title)
    host = urlparse(item.canonical_url).netloc.lower()
    if not normalized_title or not host:
        return None

    return f"{host}|{normalized_title}"


class DuplicateGate:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_duplicate(self, item: SourceItem) -> NewsItem | None:
        signature = _build_duplicate_signature(item)
        if signature is None:
            return None

        published_at = _normalize_datetime(item.published_at)
        if published_at is None:
            return None

        window_start = published_at - DUPLICATE_WINDOW
        window_end = published_at + DUPLICATE_WINDOW
        candidates = self.session.scalars(
            select(NewsItem).where(
                NewsItem.published_at.is_not(None),
                NewsItem.published_at >= window_start,
                NewsItem.published_at <= window_end,
            )
        ).all()
        for candidate in candidates:
            candidate_signature = _build_duplicate_signature(
                SourceItem(
                    title=candidate.title,
                    canonical_url=candidate.canonical_url,
                    summary=candidate.summary,
                    content_text=None,
                    published_at=candidate.published_at,
                )
            )
            if candidate_signature == signature:
                return candidate

        # 跨源模糊判重:同窗口内 SimHash 近重复标题(不要求同主机)。
        for candidate in candidates:
            if titles_look_duplicate(item.title, candidate.title):
                return candidate
        return None
