from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent.parent / "data" / "a_shares_dataset.json"

_A_SHARES_CACHE: list[dict[str, str]] | None = None
_A_SHARES_LOCK = threading.Lock()


def get_all_a_shares() -> list[dict[str, str]]:
    global _A_SHARES_CACHE
    if _A_SHARES_CACHE is not None:
        return _A_SHARES_CACHE

    with _A_SHARES_LOCK:
        if _A_SHARES_CACHE is not None:
            return _A_SHARES_CACHE

        if not DATASET_PATH.exists():
            logger.warning("a_shares_dataset.json not found at %s", DATASET_PATH)
            _A_SHARES_CACHE = []
            return _A_SHARES_CACHE

        try:
            with open(DATASET_PATH, encoding="utf-8") as f:
                items = json.load(f)
                _A_SHARES_CACHE = items
                logger.info("Loaded %d A-share stocks into memory cache", len(items))
                return items
        except Exception:
            logger.exception("Failed to load A-share dataset from %s", DATASET_PATH)
            _A_SHARES_CACHE = []
            return _A_SHARES_CACHE


def search_a_shares(query: str, limit: int = 30) -> list[dict[str, str]]:
    q = query.strip().lower()
    if not q:
        return []

    stocks = get_all_a_shares()
    if not stocks:
        return []

    scored_results: list[tuple[int, dict[str, str]]] = []
    is_numeric = q.isdigit()

    for stock in stocks:
        symbol = stock["symbol"].lower()
        digits = symbol.split(".", 1)[0]
        name = stock["display_name"].lower()
        pinyin = stock.get("pinyin", "").lower()

        score = 0

        # 精确相等最高权重
        if q == digits or q == symbol:
            score = 100
        elif not is_numeric and q == name:
            score = 95
        elif not is_numeric and pinyin and q == pinyin:
            score = 90
        # 代码前缀匹配
        elif digits.startswith(q) or symbol.startswith(q):
            score = 85
        # 名称前缀匹配
        elif not is_numeric and name.startswith(q):
            score = 80
        # 拼音前缀匹配
        elif not is_numeric and pinyin and pinyin.startswith(q):
            score = 75
        # 包含匹配
        elif q in digits or q in symbol:
            score = 65
        elif not is_numeric and q in name:
            score = 60
        elif not is_numeric and pinyin and q in pinyin:
            score = 55

        if score > 0:
            scored_results.append((score, stock))

    # 按权重倒序，若权重相同按代码升序
    scored_results.sort(key=lambda item: (-item[0], item[1]["symbol"]))

    return [stock for _, stock in scored_results[:limit]]
