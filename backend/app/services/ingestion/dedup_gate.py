from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
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


def _signature_from_parts(title: str, canonical_url: str) -> str | None:
    normalized_title = _normalize_title_for_signature(title)
    host = urlparse(canonical_url).netloc.lower()
    if not normalized_title or not host:
        return None
    return f"{host}|{normalized_title}"


def _build_duplicate_signature(item: SourceItem) -> str | None:
    # 签名不再包含小时桶:时间邻近性由 DuplicateGate.find_duplicate 的 ±DUPLICATE_WINDOW
    # 滑动窗口判定,避免 23:58 / 00:02 落在不同自然小时导致漏判。
    if _normalize_datetime(item.published_at) is None:
        return None
    return _signature_from_parts(item.title, item.canonical_url)


@dataclass
class _Candidate:
    """查重候选的轻量投影(避免加载 summary 等大文本列的完整 ORM 对象)。"""

    news_id: int
    title: str
    published_at: datetime  # 已归一化为 UTC aware
    signature: str | None


class DuplicateGate:
    """签名 + SimHash 标题相似两道闸的近重复判定。

    支持按批预取(prime / register / invalidate):批量落库前一次性查出
    本批时间范围 ±DUPLICATE_WINDOW 内的候选(仅 id/title/canonical_url/
    published_at 四列),构建签名索引供整批复用;同批内新落库的行通过
    register 增量加入索引,供后续 item 判重。未预取(或窗口未覆盖)时
    回退为单条轻量查询,语义与预取路径一致。
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._candidates: dict[int, _Candidate] | None = None
        self._by_signature: dict[str, list[int]] = {}
        self._window_start: datetime | None = None
        self._window_end: datetime | None = None

    # —— 批量索引生命周期 ——

    def prime(self, items: Iterable[SourceItem]) -> None:
        """按整批 items 的发布时间范围一次性预取查重候选。"""
        self.invalidate()
        published = [
            value
            for value in (_normalize_datetime(item.published_at) for item in items)
            if value is not None
        ]
        if not published:
            return

        window_start = min(published) - DUPLICATE_WINDOW
        window_end = max(published) + DUPLICATE_WINDOW
        rows = self.session.execute(
            select(NewsItem.id, NewsItem.title, NewsItem.canonical_url, NewsItem.published_at).where(
                NewsItem.published_at.is_not(None),
                NewsItem.published_at >= window_start,
                NewsItem.published_at <= window_end,
            )
        ).all()

        self._candidates = {}
        self._by_signature = {}
        self._window_start = window_start
        self._window_end = window_end
        for news_id, title, canonical_url, published_at in rows:
            self._add_candidate(news_id, title, canonical_url, published_at)

    def register(self, news_item: NewsItem) -> None:
        """把本批刚插入/更新的行加入索引,让同批后续 item 也能匹配到它。"""
        if self._candidates is None:
            return
        self._remove_candidate(news_item.id)
        self._add_candidate(
            news_item.id, news_item.title, news_item.canonical_url, news_item.published_at
        )

    def invalidate(self) -> None:
        self._candidates = None
        self._by_signature = {}
        self._window_start = None
        self._window_end = None

    def _add_candidate(
        self,
        news_id: int,
        title: str,
        canonical_url: str,
        published_at: datetime | None,
    ) -> None:
        published = _normalize_datetime(published_at)
        if self._candidates is None or published is None:
            return
        signature = _signature_from_parts(title, canonical_url)
        self._candidates[news_id] = _Candidate(
            news_id=news_id, title=title, published_at=published, signature=signature
        )
        if signature is not None:
            self._by_signature.setdefault(signature, []).append(news_id)

    def _remove_candidate(self, news_id: int) -> None:
        if self._candidates is None:
            return
        old = self._candidates.pop(news_id, None)
        if old is not None and old.signature is not None:
            ids = self._by_signature.get(old.signature)
            if ids and news_id in ids:
                ids.remove(news_id)

    def _index_covers(self, window_start: datetime, window_end: datetime) -> bool:
        return (
            self._candidates is not None
            and self._window_start is not None
            and self._window_end is not None
            and self._window_start <= window_start
            and window_end <= self._window_end
        )

    # —— 判重 ——

    def find_duplicate(self, item: SourceItem) -> NewsItem | None:
        signature = _build_duplicate_signature(item)
        if signature is None:
            return None

        published_at = _normalize_datetime(item.published_at)
        if published_at is None:
            return None

        window_start = published_at - DUPLICATE_WINDOW
        window_end = published_at + DUPLICATE_WINDOW

        if self._index_covers(window_start, window_end):
            match_id = self._find_in_index(item, signature, window_start, window_end)
        else:
            candidates = self._load_window_candidates(window_start, window_end)
            match_id = self._match_candidates(item, signature, candidates)

        if match_id is None:
            return None
        return self.session.get(NewsItem, match_id)

    def _find_in_index(
        self,
        item: SourceItem,
        signature: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int | None:
        assert self._candidates is not None
        # 第一道闸:host+标准化标题 精确签名(dict O(1) 命中)。
        for news_id in self._by_signature.get(signature, []):
            candidate = self._candidates.get(news_id)
            if candidate is not None and window_start <= candidate.published_at <= window_end:
                return news_id
        # 第二道闸:跨源模糊判重(同窗口内 SimHash 近重复标题,不要求同主机)。
        for candidate in self._candidates.values():
            if window_start <= candidate.published_at <= window_end and titles_look_duplicate(
                item.title, candidate.title
            ):
                return candidate.news_id
        return None

    def _load_window_candidates(
        self, window_start: datetime, window_end: datetime
    ) -> list[_Candidate]:
        rows = self.session.execute(
            select(NewsItem.id, NewsItem.title, NewsItem.canonical_url, NewsItem.published_at).where(
                NewsItem.published_at.is_not(None),
                NewsItem.published_at >= window_start,
                NewsItem.published_at <= window_end,
            )
        ).all()
        candidates: list[_Candidate] = []
        for news_id, title, canonical_url, published_at in rows:
            published = _normalize_datetime(published_at)
            if published is None:
                continue
            candidates.append(
                _Candidate(
                    news_id=news_id,
                    title=title,
                    published_at=published,
                    signature=_signature_from_parts(title, canonical_url),
                )
            )
        return candidates

    @staticmethod
    def _match_candidates(
        item: SourceItem, signature: str, candidates: list[_Candidate]
    ) -> int | None:
        # 第一道闸:精确签名。
        for candidate in candidates:
            if candidate.signature == signature:
                return candidate.news_id
        # 第二道闸:跨源模糊判重(SimHash 近重复标题,不要求同主机)。
        for candidate in candidates:
            if titles_look_duplicate(item.title, candidate.title):
                return candidate.news_id
        return None
