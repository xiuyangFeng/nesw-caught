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
    {
        "symbol": "600519.SH",
        "display_name": "贵州茅台",
        "market": "cn",
        "aliases": ["茅台", "贵州茅台", "600519", "sh600519", "kweichow moutai"],
    },
    {
        "symbol": "300750.SZ",
        "display_name": "宁德时代",
        "market": "cn",
        "aliases": ["宁德时代", "300750", "sz300750", "catl"],
    },
    {
        "symbol": "000001.SZ",
        "display_name": "平安银行",
        "market": "cn",
        "aliases": ["平安银行", "000001", "sz000001", "ping an bank"],
    },
    {
        "symbol": "600036.SH",
        "display_name": "招商银行",
        "market": "cn",
        "aliases": ["招商银行", "600036", "sh600036", "cmb"],
    },
    {
        "symbol": "601318.SH",
        "display_name": "中国平安",
        "market": "cn",
        "aliases": ["中国平安", "601318", "sh601318", "ping an insurance"],
    },
    {
        "symbol": "002594.SZ",
        "display_name": "比亚迪",
        "market": "cn",
        "aliases": ["比亚迪", "002594", "sz002594", "byd"],
    },
    {
        "symbol": "688041.SH",
        "display_name": "海光信息",
        "market": "cn",
        "aliases": ["海光信息", "688041", "sh688041", "haiguang"],
    },
    {
        "symbol": "688981.SH",
        "display_name": "中芯国际",
        "market": "cn",
        "aliases": ["中芯国际", "688981", "sh688981", "smic"],
    },
]


def list_watchlist_candidates() -> list[dict[str, object]]:
    return WATCHLIST_CANDIDATES
