"""`url_hash` 计算方式必须在所有落库/查询路径上保持一致。

背景：`persister.persist_item` 改为「先 `normalize_url_for_hash` 再 sha256」之后，
另外两条路径仍在用未归一化的原始 URL 算 hash：
- `stock_news_search`（搜索结果落库）→ 同一篇文章经搜索路径与抓取路径算出不同 hash，
  唯一闸失效，重复插入；
- `detail_hydration`（MiniMax 详情水合）→ 查不到既有行，水合白跑、冷却表失效。

这类"同一个不变量散落在多处各写一遍"的漂移不会被任何现有用例发现（各自的单测都
只验证自己那一份），所以这里用源码级断言把三处钉在一起。
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from app.services.ingestion.dedup_gate import normalize_url_for_hash

_APP_DIR = Path(__file__).resolve().parents[1] / "app"

# 所有会计算 url_hash 的模块，都必须经过 normalize_url_for_hash。
_HASH_CALL_SITES = (
    "services/ingestion/persister.py",
    "services/ingestion/detail_hydration.py",
    "services/stock_news_search.py",
)


def test_all_url_hash_call_sites_normalize_first() -> None:
    """任何对 canonical_url 直接 sha256 而不先归一化的写法都应被拦下。"""
    offenders: list[str] = []
    for rel in _HASH_CALL_SITES:
        source = (_APP_DIR / rel).read_text(encoding="utf-8")
        # 匹配 sha256(<something>canonical_url...) 且括号内不含 normalize_url_for_hash
        for match in re.finditer(r"sha256\(([^)]*canonical_url[^)]*)\)", source):
            if "normalize_url_for_hash" not in match.group(1):
                offenders.append(f"{rel}: sha256({match.group(1)})")
    assert not offenders, (
        "以下位置直接对未归一化的 canonical_url 计算 url_hash，会与 persister 落库的 "
        "hash 对不上：\n" + "\n".join(offenders)
    )


def test_normalization_collapses_tracking_params() -> None:
    """归一化必须让只差跟踪参数的两个 URL 得到同一个 hash。"""
    plain = "https://example.com/news/story-1"
    tracked = "https://example.com/news/story-1?utm_source=rss&utm_medium=feed"

    def h(url: str) -> str:
        return sha256(normalize_url_for_hash(url).encode("utf-8")).hexdigest()

    assert h(plain) == h(tracked)


def test_normalization_keeps_meaningful_query_distinct() -> None:
    """文章 id 在 query 里的站点不能被误合并（不能整片剥 query）。"""

    def h(url: str) -> str:
        return sha256(normalize_url_for_hash(url).encode("utf-8")).hexdigest()

    assert h("https://example.com/a?id=1") != h("https://example.com/a?id=2")
