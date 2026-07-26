import time

from app.services.a_share_search_service import get_all_a_shares, search_a_shares


def test_get_all_a_shares_loaded() -> None:
    stocks = get_all_a_shares()
    assert len(stocks) >= 5000, f"Expected > 5000 A-shares, got {len(stocks)}"
    symbols = {s["symbol"] for s in stocks}
    assert "600519.SH" in symbols
    assert "000858.SZ" in symbols
    assert "300750.SZ" in symbols


def test_search_a_shares_by_code() -> None:
    results = search_a_shares("600519")
    assert len(results) > 0
    assert results[0]["symbol"] == "600519.SH"
    assert "贵州茅台" in results[0]["display_name"]


def test_search_a_shares_by_pinyin() -> None:
    results = search_a_shares("gzmt")
    assert len(results) > 0
    assert results[0]["symbol"] == "600519.SH"

    results_wly = search_a_shares("wly")
    assert len(results_wly) > 0
    assert results_wly[0]["symbol"] == "000858.SZ"


def test_search_a_shares_by_name() -> None:
    results = search_a_shares("宁德时代")
    assert len(results) > 0
    assert results[0]["symbol"] == "300750.SZ"


def test_search_a_shares_performance() -> None:
    # 连续执行 100 次内存搜索，验证总耗时小于 100ms
    start = time.perf_counter()
    queries = ["600519", "gzmt", "wly", "000858", "300750", "payh", "平安", "长电", "600900", "000001"]
    for _ in range(10):
        for q in queries:
            _ = search_a_shares(q)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.3, f"100 searches took {elapsed:.4f}s, expected < 0.3s"
