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
        "symbol": "000858.SZ",
        "display_name": "五粮液",
        "market": "cn",
        "aliases": ["五粮液", "000858", "sz000858", "wuliangye"],
    },
    {
        "symbol": "300559.SZ",
        "display_name": "东方财富",
        "market": "cn",
        "aliases": ["东方财富", "东财", "300559", "sz300559", "east money"],
    },
    {
        "symbol": "600900.SH",
        "display_name": "长江电力",
        "market": "cn",
        "aliases": ["长江电力", "长电", "600900", "sh600900", "yangtze power"],
    },
    {
        "symbol": "600030.SH",
        "display_name": "中信证券",
        "market": "cn",
        "aliases": ["中信证券", "600030", "sh600030", "citic securities"],
    },
    {
        "symbol": "601138.SH",
        "display_name": "工业富联",
        "market": "cn",
        "aliases": ["工业富联", "富士康", "601138", "sh601138", "foxconn industrial internet"],
    },
    {
        "symbol": "688256.SH",
        "display_name": "寒武纪",
        "market": "cn",
        "aliases": ["寒武纪", "688256", "sh688256", "cambricon"],
    },
    {
        "symbol": "002475.SZ",
        "display_name": "立讯精密",
        "market": "cn",
        "aliases": ["立讯精密", "立讯", "002475", "sz002475", "luxshare"],
    },
    {
        "symbol": "603986.SH",
        "display_name": "兆易创新",
        "market": "cn",
        "aliases": ["兆易创新", "兆易", "603986", "sh603986", "giga device"],
    },
    {
        "symbol": "002230.SZ",
        "display_name": "科大讯飞",
        "market": "cn",
        "aliases": ["科大讯飞", "讯飞", "002230", "sz002230", "iflytek"],
    },
    {
        "symbol": "603259.SH",
        "display_name": "药明康德",
        "market": "cn",
        "aliases": ["药明康德", "药明", "603259", "sh603259", "wuxi apptec"],
    },
    {
        "symbol": "300760.SZ",
        "display_name": "迈瑞医疗",
        "market": "cn",
        "aliases": ["迈瑞医疗", "迈瑞", "300760", "sz300760", "mindray"],
    },
    {
        "symbol": "601899.SH",
        "display_name": "紫金矿业",
        "market": "cn",
        "aliases": ["紫金矿业", "紫金", "601899", "sh601899", "zijin mining"],
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
        "aliases": ["海光信息", "海光", "688041", "sh688041", "haiguang"],
    },
    {
        "symbol": "688981.SH",
        "display_name": "中芯国际",
        "market": "cn",
        "aliases": ["中芯国际", "中芯", "688981", "sh688981", "smic"],
    },
]


def list_watchlist_candidates() -> list[dict[str, object]]:
    return WATCHLIST_CANDIDATES

