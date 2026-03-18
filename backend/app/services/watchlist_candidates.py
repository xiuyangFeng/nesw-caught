from __future__ import annotations


WATCHLIST_CANDIDATES: list[dict[str, object]] = [
    {
        "symbol": "0700.HK",
        "display_name": "Tencent",
        "market": "hk",
        "aliases": ["腾讯", "腾讯控股", "700", "0700", "tencent holdings"],
    },
    {
        "symbol": "9988.HK",
        "display_name": "Alibaba",
        "market": "hk",
        "aliases": ["阿里", "阿里巴巴", "9988", "baba", "alibaba group"],
    },
    {
        "symbol": "AAPL",
        "display_name": "Apple",
        "market": "us",
        "aliases": ["苹果", "apple inc"],
    },
    {
        "symbol": "NVDA",
        "display_name": "NVIDIA",
        "market": "us",
        "aliases": ["英伟达", "nvidia corp"],
    },
    {
        "symbol": "TME",
        "display_name": "Tencent Music",
        "market": "us",
        "aliases": ["腾讯音乐", "tencent music entertainment"],
    },
    {
        "symbol": "TSLA",
        "display_name": "Tesla",
        "market": "us",
        "aliases": ["特斯拉", "tesla inc"],
    },
]


def list_watchlist_candidates() -> list[dict[str, object]]:
    return WATCHLIST_CANDIDATES
