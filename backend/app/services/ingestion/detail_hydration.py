from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.services import http_pool
from app.services.ingestion.dedup_gate import normalize_url_for_hash
from app.services.ingestion.parser import _parse_minimax_detail_html
from app.services.ingestion.types import SourceDefinition, SourceItem

logger = logging.getLogger(__name__)

MINIMAX_SOURCE_NAME = "MiniMax News"

# 同一 detail URL 在 24h 窗口内最多重试次数;超出后进入冷却,不再每轮重抓。
DETAIL_FETCH_MAX_ATTEMPTS = 3
DETAIL_FETCH_WINDOW_SECONDS = 86400.0
_DETAIL_FETCH_WORKERS = 4


class DetailFetchCooldown:
    """item 级内存冷却表:持续失败的 detail URL 在窗口内限制重试次数。"""

    def __init__(
        self,
        *,
        max_attempts: int = DETAIL_FETCH_MAX_ATTEMPTS,
        window_seconds: float = DETAIL_FETCH_WINDOW_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, url: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        attempts = [ts for ts in self._failures.get(url, []) if ts >= cutoff]
        if attempts:
            self._failures[url] = attempts
        else:
            self._failures.pop(url, None)
        return attempts

    def allow(self, url: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            return len(self._prune(url, now)) < self.max_attempts

    def record_failure(self, url: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._prune(url, now)
            attempts.append(now)
            self._failures[url] = attempts

    def record_success(self, url: str) -> None:
        with self._lock:
            self._failures.pop(url, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


minimax_detail_cooldown = DetailFetchCooldown()


def clear_detail_fetch_cooldowns() -> None:
    """测试钩子:清空 item 级冷却表。"""
    minimax_detail_cooldown.clear()


def _article_looks_complete(article: ArticleContent | None) -> bool:
    return (
        article is not None
        and article.extract_status == "success"
        and not (article.content_text or "").startswith("模型 文本 ")
    )


def hydrate_minimax_detail_items(
    session: Session,
    source: SourceDefinition,
    items: list[SourceItem],
    *,
    cooldown: DetailFetchCooldown | None = None,
    max_workers: int = _DETAIL_FETCH_WORKERS,
) -> list[SourceItem]:
    """并发水合 MiniMax 详情页。

    数据库读取(判断已存在记录是否完整)集中在调用方线程批量完成;
    工作线程只做网络抓取与 HTML 解析,不触碰 session(SQLite 单写约束)。
    已完整的记录与冷却中的 URL 不发请求。
    """
    if not items:
        return items

    cooldown = cooldown if cooldown is not None else minimax_detail_cooldown

    # 必须与 persister.persist_item 用同一套归一化后再算 hash，否则带跟踪参数的
    # URL 在这里算出的 hash 与库里实际存的对不上，既有行会查不到 → 详情水合白跑、
    # 冷却表也失效。
    url_hashes = [
        sha256(normalize_url_for_hash(item.canonical_url).encode("utf-8")).hexdigest() for item in items
    ]
    existing_rows = session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))).all()
    existing_by_hash = {row.url_hash: row for row in existing_rows}
    article_by_news_id: dict[int, ArticleContent] = {}
    if existing_rows:
        article_rows = session.scalars(
            select(ArticleContent).where(ArticleContent.news_id.in_([row.id for row in existing_rows]))
        ).all()
        article_by_news_id = {row.news_id: row for row in article_rows}

    fetch_indices: list[int] = []
    for index, item in enumerate(items):
        existing = existing_by_hash.get(url_hashes[index])
        if existing is not None:
            article = article_by_news_id.get(existing.id)
            if existing.published_at is not None and _article_looks_complete(article):
                continue
        if not cooldown.allow(item.canonical_url):
            logger.info("minimax detail hydration skipped by cooldown: url=%s", item.canonical_url)
            continue
        fetch_indices.append(index)

    if not fetch_indices:
        return items

    client = http_pool.get_feed_client()

    def _fetch(index: int) -> tuple[int, SourceItem | None, str | None]:
        item = items[index]
        try:
            response = client.get(item.canonical_url)
            response.raise_for_status()
            detail_item = _parse_minimax_detail_html(
                response.text,
                source,
                canonical_url=item.canonical_url,
                fallback_title=item.title,
            )
            return index, detail_item, None
        except Exception as exc:
            # 兜底范围刻意保持宽泛:失败时优雅降级为回退 item(而非向上抛出),
            # 不因单条 MiniMax 详情页失败拖垮整批。可能的异常包括 httpx 网络层
            # (含不属于 httpx.HTTPError 体系的 httpx.InvalidURL/StreamError 等)
            # 与 _parse_minimax_detail_html 显式抛出的 ValueError,类型面无法安全
            # 穷举收窄,因此维持 Exception 兜底。
            return index, None, str(exc)

    hydrated = list(items)
    workers = min(max_workers, len(fetch_indices))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="minimax-detail") as pool:
        for index, detail_item, error in pool.map(_fetch, fetch_indices):
            item = items[index]
            existing = existing_by_hash.get(url_hashes[index])
            if error is not None:
                cooldown.record_failure(item.canonical_url)
                logger.warning(
                    "minimax detail hydration failed: source=%s url=%s error=%s",
                    source.name,
                    item.canonical_url,
                    error,
                )
                if existing is not None and existing.published_at is not None:
                    # 已存在记录有发布时间:保留原 item,不覆盖为失败态。
                    continue
                hydrated[index] = SourceItem(
                    title=item.title,
                    canonical_url=item.canonical_url,
                    summary=item.summary,
                    content_text=None,
                    content_html=None,
                    published_at=item.published_at,
                    extract_status="failed",
                    extract_error=error,
                )
                continue

            cooldown.record_success(item.canonical_url)
            if existing is not None and existing.summary and not detail_item.summary:
                detail_item = SourceItem(
                    title=detail_item.title,
                    canonical_url=detail_item.canonical_url,
                    summary=existing.summary,
                    content_text=detail_item.content_text,
                    published_at=detail_item.published_at,
                    content_html=detail_item.content_html,
                    extract_status=detail_item.extract_status,
                    extract_error=detail_item.extract_error,
                )
            hydrated[index] = detail_item
    return hydrated
