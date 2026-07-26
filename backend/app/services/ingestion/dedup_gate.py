from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.services.ingestion.types import DUPLICATE_WINDOW, SourceItem
from app.services.ingestion.utils import _normalize_datetime, _utc_now
from app.services.news_dedup import titles_look_duplicate

logger = logging.getLogger(__name__)

# 与 NewsItem.title 的 String(500) 对齐。
#
# 修复 P2-2：persister 用 `item.title[:500]` 截断入库，而签名此前基于【未截断】
# 标题计算 —— 超长标题的历史行(库里存的是截断版)与新行(签名用全长)签名不一致，
# 精确签名这道闸直接漏杀。这里统一：任何签名都先截断到同一长度再归一化。
TITLE_SIGNATURE_MAX_LENGTH = 500

# 整批 prime 窗口上限。
#
# 修复 P1-3：prime 用整批 min(published)-60min ~ max(published)+60min 作窗口。
# 实测库里 WSJ 的条目 published 全在 2025-01、MarketWatch MarketPulse 在
# 2024-10/11 —— 一旦某批混入一条陈旧条目，窗口就横跨一年多，prime 会把区间内
# 【所有】news_item 拉进内存，随后第二道闸对每个 item 遍历全部候选。
# 超过该跨度就不预取，退化为 find_duplicate 的「逐条 ±60 分钟小窗口查询」。
MAX_PRIME_WINDOW = timedelta(hours=6)

# —— URL 归一化(P1-2) ——
#
# 同一篇文章带不同 utm 参数会算出不同 url_hash，精确去重直接失效。
# 采用【黑名单】而非白名单：有些站点的文章 id 就在 query 里(如 ?id=123)，
# 一刀切剥掉 query 会把不同文章合并成同一条，比漏杀更危险。
_TRACKING_QUERY_PARAMS = frozenset(
    {
        "from",
        "src",
        "ref",
        "referer",
        "referrer",
        "spm",
        "share",
        "shareid",
        "share_token",
        "scene",
        "clicktime",
        "enterid",
        "gclid",
        "fbclid",
        "yclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "cmpid",
        "ncid",
        "smid",
        "_hsenc",
        "_hsmi",
        "f",
    }
)
_TRACKING_QUERY_PREFIXES = ("utm_", "share_", "spm_", "mtm_", "pk_")

# 判重签名的 host 归一化：移动版/AMP/www 镜像视为同一主机。
# 注意：这里【只】用于判重签名，不参与 url_hash，也不改写入库的 canonical_url。
_HOST_MIRROR_PREFIXES = ("www.", "m.", "amp.", "mobile.")

_DEFAULT_PORTS = {"http": "80", "https": "443"}


def _is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    return lowered in _TRACKING_QUERY_PARAMS or lowered.startswith(_TRACKING_QUERY_PREFIXES)


def normalize_url_for_hash(url: str) -> str:
    """url_hash 用的 URL 归一化(P1-2)。

    做：小写 scheme/host、去默认端口、去 fragment、剥离已知跟踪参数、
    参数排序、去掉多余的末尾斜杠。
    不做：剥 www./m. 前缀(会改变 host 语义，且部分站点镜像内容并不一致)、
    不做整片剥 query(文章 id 可能就在 query 里)。
    """
    raw = (url or "").strip()
    if not raw:
        return raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    if not parts.scheme or not parts.netloc:
        return raw

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    default_port = _DEFAULT_PORTS.get(scheme)
    if default_port and netloc.endswith(f":{default_port}"):
        netloc = netloc[: -(len(default_port) + 1)]

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(query_pairs))

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, query, ""))


def _signature_host(canonical_url: str) -> str:
    host = urlsplit(canonical_url or "").netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    for prefix in _HOST_MIRROR_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    return host


def _normalize_title_for_signature(title: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", (title or "")[:TITLE_SIGNATURE_MAX_LENGTH].lower())
    return " ".join(normalized.split())


def _signature_from_parts(title: str, canonical_url: str) -> str | None:
    normalized_title = _normalize_title_for_signature(title)
    host = _signature_host(canonical_url)
    if not normalized_title or not host:
        return None
    return f"{host}|{normalized_title}"


def _build_duplicate_signature(item: SourceItem) -> str | None:
    # 签名不再包含小时桶:时间邻近性由 DuplicateGate.find_duplicate 的 ±DUPLICATE_WINDOW
    # 滑动窗口判定,避免 23:58 / 00:02 落在不同自然小时导致漏判。
    #
    # 修复 P1：此前签名要求 published_at 非空，导致 published_at 为 NULL 的新闻
    # (实测 36Kr 202 条、MiniMax 3 条全是 NULL) 100% 不参与去重，只剩 url_hash
    # 精确去重 —— 换个 utm 参数就是一条新新闻。现在签名不再看时间，
    # 时间维度由 find_duplicate 用 effective_at(published_at 兜底 fetched_at) 判定。
    return _signature_from_parts(item.title, item.canonical_url)


@dataclass
class _Candidate:
    """查重候选的轻量投影(避免加载 summary 等大文本列的完整 ORM 对象)。"""

    news_id: int
    title: str
    effective_at: datetime  # 已归一化为 UTC aware,= published_at or fetched_at
    signature: str | None


class DuplicateGate:
    """签名 + SimHash 标题相似两道闸的近重复判定。

    支持按批预取(prime / register / invalidate):批量落库前一次性查出
    本批时间范围 ±DUPLICATE_WINDOW 内的候选(仅 id/title/canonical_url/
    effective_at 四列),构建签名索引供整批复用;同批内新落库的行通过
    register 增量加入索引,供后续 item 判重。未预取(或窗口未覆盖、
    或整批跨度超过 MAX_PRIME_WINDOW)时回退为单条轻量查询,语义与预取路径一致。

    时间维度统一用 effective_at(= published_at or fetched_at):
    published_at 为空的条目照样参与判重,不再"整类新闻裸奔"。
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._candidates: dict[int, _Candidate] | None = None
        self._by_signature: dict[str, list[int]] = {}
        self._window_start: datetime | None = None
        self._window_end: datetime | None = None
        self._batch_now: datetime | None = None
        # 可观测性:最近一次 prime 的窗口与跳过原因(供运维日志与测试断言)。
        self.last_prime_window: tuple[datetime, datetime] | None = None
        self.last_prime_skipped_reason: str | None = None

    # —— 批量索引生命周期 ——

    def prime(self, items: Iterable[SourceItem]) -> None:
        """按整批 items 的生效时间范围一次性预取查重候选。"""
        self.invalidate()
        batch_now = _utc_now()
        self._batch_now = batch_now
        effective = [self._item_effective_time(item, batch_now) for item in items]
        if not effective:
            return

        window_start = min(effective) - DUPLICATE_WINDOW
        window_end = max(effective) + DUPLICATE_WINDOW
        self.last_prime_window = (window_start, window_end)
        if window_end - window_start > MAX_PRIME_WINDOW:
            # 批内混入陈旧条目(如 published 停留在 2024-10 的 MarketPulse)会把窗口
            # 撑到跨年,prime 将退化为全表加载。此时放弃预取,交给逐条小窗口查询。
            self.last_prime_skipped_reason = "window_too_wide"
            logger.info(
                "duplicate gate prime skipped: window too wide start=%s end=%s span_hours=%.1f items=%s",
                window_start,
                window_end,
                (window_end - window_start).total_seconds() / 3600,
                len(effective),
            )
            return

        rows = self._load_window_rows(window_start, window_end)

        self._candidates = {}
        self._by_signature = {}
        self._window_start = window_start
        self._window_end = window_end
        for news_id, title, canonical_url, effective_at in rows:
            self._add_candidate(news_id, title, canonical_url, effective_at)

    def register(self, news_item: NewsItem) -> None:
        """把本批刚插入/更新的行加入索引,让同批后续 item 也能匹配到它。"""
        if self._candidates is None:
            return
        self._remove_candidate(news_item.id)
        self._add_candidate(
            news_item.id,
            news_item.title,
            news_item.canonical_url,
            news_item.effective_at or news_item.published_at or news_item.fetched_at,
        )

    def invalidate(self) -> None:
        self._candidates = None
        self._by_signature = {}
        self._window_start = None
        self._window_end = None
        self._batch_now = None
        self.last_prime_window = None
        self.last_prime_skipped_reason = None

    # —— 内部工具 ——

    @staticmethod
    def _item_effective_time(item: SourceItem, fallback: datetime) -> datetime:
        """条目的判重时间轴:published_at 优先,为空时退回抓取时刻。"""
        return _normalize_datetime(item.published_at) or fallback

    def _load_window_rows(self, window_start: datetime, window_end: datetime):
        return self.session.execute(
            select(
                NewsItem.id, NewsItem.title, NewsItem.canonical_url, NewsItem.effective_at
            ).where(
                NewsItem.effective_at >= window_start,
                NewsItem.effective_at <= window_end,
            )
        ).all()

    def _add_candidate(
        self,
        news_id: int,
        title: str,
        canonical_url: str,
        effective_at: datetime | None,
    ) -> None:
        effective = _normalize_datetime(effective_at)
        if self._candidates is None or effective is None:
            return
        signature = _signature_from_parts(title, canonical_url)
        self._candidates[news_id] = _Candidate(
            news_id=news_id, title=title, effective_at=effective, signature=signature
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

        effective_at = self._item_effective_time(item, self._batch_now or _utc_now())
        window_start = effective_at - DUPLICATE_WINDOW
        window_end = effective_at + DUPLICATE_WINDOW

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
            if candidate is not None and window_start <= candidate.effective_at <= window_end:
                return news_id
        # 第二道闸:跨源模糊判重(同窗口内 SimHash 近重复标题,不要求同主机)。
        for candidate in self._candidates.values():
            if window_start <= candidate.effective_at <= window_end and titles_look_duplicate(
                item.title, candidate.title
            ):
                return candidate.news_id
        return None

    def _load_window_candidates(
        self, window_start: datetime, window_end: datetime
    ) -> list[_Candidate]:
        rows = self._load_window_rows(window_start, window_end)
        candidates: list[_Candidate] = []
        for news_id, title, canonical_url, effective_at in rows:
            effective = _normalize_datetime(effective_at)
            if effective is None:
                continue
            candidates.append(
                _Candidate(
                    news_id=news_id,
                    title=title,
                    effective_at=effective,
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
