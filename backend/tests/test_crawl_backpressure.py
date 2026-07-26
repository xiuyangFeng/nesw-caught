"""正文抓取的「解析背压」回归测试。

背景（FIX-B）：`crawl_and_extract_article` 分成两段——
  * 网络抓取：阻塞在 socket 上会释放 GIL，按 news_crawl_max_workers 高并发；
  * HTML 解析：BeautifulSoup 建树 / decompose / 选择器匹配 / get_text 是纯 CPU，
    全程持有 GIL（本环境未装 lxml，退回纯 Python 的 html.parser，实测
    cpu/wall ≈ 1.00）。

改造前两段共用同一个 8 并发线程池，8 个线程同时解析几百 KB 的 HTML 会把 uvicorn
事件循环和处理只读请求的 anyio 线程一起饿死（实测 /api/news/runtime 的 p50 从
~2ms 恶化到 200~800ms）。现在解析阶段被一个独立的模块级信号量限流到
news_crawl_parse_concurrency（默认 2），网络阶段并发不变。

这些用例锁定三件事：解析并发确实受限、网络并发不受牵连、抽取结果与限流前一致。
"""

import threading
import time
from types import SimpleNamespace

import pytest

from app.services.ingestion import article_crawler
from app.services.ingestion.article_crawler import (
    ArticleQualityError,
    _extract_article_text,
    _truncate_oversized_html,
    crawl_and_extract_article,
    reset_parse_semaphore,
)

# ---------------------------------------------------------------------------
# 测试脚手架
# ---------------------------------------------------------------------------

SIMPLE_HTML = """
<html><head><title>t</title></head><body>
  <header><nav>导航栏 Navigation</nav></header>
  <article>
    <h1>某公司发布季度财报</h1>
    <p>第一段：公司本季度营收同比增长显著，主要来自云业务与广告业务的共同拉动。</p>
    <p>第二段：管理层在电话会议上表示，下一季度的资本开支将进一步向 AI 基础设施倾斜。</p>
  </article>
  <footer><p>Footer copyright 2026</p></footer>
</body></html>
"""


@pytest.fixture(autouse=True)
def _restore_parse_semaphore():
    """每个用例前后都把模块级信号量清干净，避免污染同进程的其它测试。"""
    reset_parse_semaphore()
    yield
    reset_parse_semaphore()


def _patch_settings(monkeypatch, **overrides):
    """只覆盖 article_crawler 读取的那几个配置项，避免动全局 lru_cache。"""
    defaults = {
        "news_crawl_parse_concurrency": 2,
        "news_crawl_max_html_chars": article_crawler.DEFAULT_MAX_HTML_CHARS,
        "crawl_timeout_seconds": 15.0,
    }
    defaults.update(overrides)
    monkeypatch.setattr(article_crawler, "get_settings", lambda: SimpleNamespace(**defaults))
    reset_parse_semaphore()


class _ConcurrencyTracker:
    """记录同时进入临界区的线程数及其峰值。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        with self._lock:
            self.current -= 1


def _run_in_threads(target, count: int) -> tuple[list, float]:
    """并发跑 count 个 target()，返回 (结果列表, 总墙钟秒数)。"""
    results: list = [None] * count
    errors: list = []

    def runner(idx: int) -> None:
        try:
            results[idx] = target(idx)
        except BaseException as exc:  # noqa: BLE001 - 线程内异常必须回传，否则用例假绿
            errors.append(exc)

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(count)]
    started = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    elapsed = time.perf_counter() - started
    if errors:
        raise errors[0]
    return results, elapsed


# ---------------------------------------------------------------------------
# 1. 解析并发上限生效
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capacity", [1, 2, 3])
def test_parse_concurrency_is_capped_by_setting(monkeypatch, capacity):
    """N 个线程同时爬取时，同时进入解析临界区的线程数不得超过配置值。"""
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=capacity)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: SIMPLE_HTML)

    tracker = _ConcurrencyTracker()
    real_bs = article_crawler.BeautifulSoup

    def tracking_bs(*args, **kwargs):
        # 在解析临界区内停留足够久，让所有线程都有机会挤进来（若没有限流的话）
        tracker.enter()
        try:
            time.sleep(0.05)
            return real_bs(*args, **kwargs)
        finally:
            tracker.leave()

    monkeypatch.setattr(article_crawler, "BeautifulSoup", tracking_bs)

    results, _ = _run_in_threads(lambda i: crawl_and_extract_article(f"https://example.com/{i}"), 8)

    assert tracker.peak <= capacity, f"解析并发峰值 {tracker.peak} 超过配置上限 {capacity}"
    assert tracker.current == 0, "所有解析槽位都应被释放"
    assert all("第一段" in r for r in results)


def test_parse_slot_reaches_configured_capacity(monkeypatch):
    """限流不能过度：配额为 3 时确实允许 3 个线程并行解析，而不是退化成串行。"""
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=3)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: SIMPLE_HTML)

    barrier = threading.Barrier(3, timeout=10)
    real_bs = article_crawler.BeautifulSoup

    def tracking_bs(*args, **kwargs):
        # 3 个线程必须能同时站在 barrier 上，否则说明并行度不足 3
        barrier.wait()
        return real_bs(*args, **kwargs)

    monkeypatch.setattr(article_crawler, "BeautifulSoup", tracking_bs)

    results, _ = _run_in_threads(lambda i: crawl_and_extract_article(f"https://example.com/{i}"), 3)
    assert all("第一段" in r for r in results)


def test_parse_slot_released_on_parse_failure(monkeypatch):
    """解析抛异常也必须归还槽位，否则几次失败就会把配额漏干、整条管线卡死。"""
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=1)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: SIMPLE_HTML)

    def exploding_bs(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(article_crawler, "BeautifulSoup", exploding_bs)
    for _ in range(3):
        with pytest.raises(RuntimeError, match="Webpage parse failed"):
            crawl_and_extract_article("https://example.com/boom")

    # 槽位没漏的话，恢复正常解析后应立刻返回而不是阻塞
    monkeypatch.undo()
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=1)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: SIMPLE_HTML)
    assert "第一段" in crawl_and_extract_article("https://example.com/ok")


def test_parse_semaphore_rebuilds_when_capacity_changes(monkeypatch):
    """配置容量变化后信号量应重建，不能一直沿用进程启动时的旧配额。"""
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=1)
    first = article_crawler._get_parse_semaphore()
    assert article_crawler._get_parse_semaphore() is first  # 容量不变则复用

    _patch_settings(monkeypatch, news_crawl_parse_concurrency=4)
    assert article_crawler._get_parse_semaphore() is not first


# ---------------------------------------------------------------------------
# 2. 网络并发不受解析信号量限制
# ---------------------------------------------------------------------------


def test_network_fetch_is_not_serialized_by_parse_semaphore(monkeypatch):
    """8 路慢速抓取的总耗时应接近单次耗时（max），而不是排队累加（sum）。

    解析配额只有 2，如果信号量错误地包住了网络阶段，8 次 0.3s 的抓取至少要
    8/2*0.3 = 1.2s；正确实现下网络全并发，总耗时 ≈ 0.3s。
    """
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=2)

    fetch_delay = 0.3

    def slow_fetch(url, timeout):
        time.sleep(fetch_delay)
        return SIMPLE_HTML

    monkeypatch.setattr(article_crawler, "_fetch_article_html", slow_fetch)

    results, elapsed = _run_in_threads(
        lambda i: crawl_and_extract_article(f"https://example.com/slow/{i}"), 8
    )

    assert all("第一段" in r for r in results)
    assert elapsed >= fetch_delay, "总耗时不应小于单次抓取耗时"
    # 串行化（哪怕只是 2 路）的下界是 1.2s；给 CI 抖动留足余量后仍能清晰区分
    assert elapsed < fetch_delay * 3, f"网络抓取疑似被解析信号量串行化：elapsed={elapsed:.3f}s"


# ---------------------------------------------------------------------------
# 3. 超大 HTML 截断
# ---------------------------------------------------------------------------


TRUNCATION_LIMIT = 4000


def _oversized_html(tail_paragraphs: int = 4000) -> str:
    """正文在文档前部，后面拖着一条巨长的尾巴（模拟聚合页 / 无限滚动快照）。

    刻意不用 <article> 之类的精确选择器，让抽取走密度兜底路径——这样抽取结果的
    长度直接反映「实际被解析了多少 HTML」，截断断言才不是空断言。
    """
    tail = "\n".join(
        f"<div class='row'><p>尾部噪声段落 {i}：这一段用于把整篇文档撑到远远超过截断上限，"
        f"长度必须超过密度兜底法的二十五字符门槛。</p></div>"
        for i in range(tail_paragraphs)
    )
    return (
        "<html><body><div id='lead'><p>开头正文：这一段位于整篇文档的最前部，"
        "无论是否发生截断都应当被完整抽取出来，长度也超过二十五字符门槛。</p></div><section>"
        + tail
        + "<div class='row'><p>LAST_MARKER：这是整篇文档的最后一段，位于截断点之后，"
        "长度同样超过二十五字符门槛。</p></div>"
        "</section></body></html>"
    )


def test_oversized_html_is_truncated_before_parse(monkeypatch):
    html = _oversized_html()
    assert len(html) > TRUNCATION_LIMIT * 10  # 确保这是一次真正的「超大页面」

    # 不设限时：整篇都被解析，抽取结果远超上限
    _patch_settings(monkeypatch, news_crawl_max_html_chars=0)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: html)
    unlimited = crawl_and_extract_article("https://example.com/huge")
    assert len(unlimited) > TRUNCATION_LIMIT * 10
    assert "LAST_MARKER" in unlimited

    # 设限后：只解析前 limit 个字符，正文开头保住，截断点之后的内容消失
    _patch_settings(monkeypatch, news_crawl_max_html_chars=TRUNCATION_LIMIT)
    truncated = crawl_and_extract_article("https://example.com/huge")
    assert "开头正文" in truncated
    assert "LAST_MARKER" not in truncated, "截断点之后的内容不应进入解析结果"
    assert len(truncated) < TRUNCATION_LIMIT, "抽取结果应受截断上限约束"


def test_truncate_helper_respects_limit_semantics(monkeypatch):
    html = "x" * 500
    _patch_settings(monkeypatch, news_crawl_max_html_chars=100)
    assert len(_truncate_oversized_html(html, url="u")) == 100
    # 未超限的页面原样返回（不复制、不改写）
    _patch_settings(monkeypatch, news_crawl_max_html_chars=1000)
    assert _truncate_oversized_html(html, url="u") is html
    # <= 0 表示关闭限制
    _patch_settings(monkeypatch, news_crawl_max_html_chars=0)
    assert _truncate_oversized_html(html, url="u") is html
    _patch_settings(monkeypatch, news_crawl_max_html_chars=-1)
    assert _truncate_oversized_html(html, url="u") is html


def test_oversized_item_does_not_affect_siblings_in_batch(monkeypatch):
    """一条超大页面混在批次里，其余条目的抽取结果不受影响。"""
    huge = _oversized_html()

    _patch_settings(
        monkeypatch,
        news_crawl_parse_concurrency=2,
        news_crawl_max_html_chars=TRUNCATION_LIMIT,
    )

    def fetch(url, timeout):
        return huge if url.endswith("/huge") else SIMPLE_HTML

    monkeypatch.setattr(article_crawler, "_fetch_article_html", fetch)

    urls = [f"https://example.com/n{i}" for i in range(7)]
    urls.insert(3, "https://example.com/huge")
    results, _ = _run_in_threads(lambda i: crawl_and_extract_article(urls[i]), len(urls))

    for url, result in zip(urls, results, strict=True):
        if url.endswith("/huge"):
            assert "开头正文" in result and "LAST_MARKER" not in result
        else:
            assert "第一段" in result and "第二段" in result
            assert "导航栏" not in result and "Footer copyright" not in result


# ---------------------------------------------------------------------------
# 4. 既有抽取行为不变
# ---------------------------------------------------------------------------

DENSITY_FALLBACK_HTML = """
<html><body>
  <div id="wrapper">
    <p>密度兜底段落一：这是一段长度超过二十五个字符的正文内容，应当被密度兜底法收集。</p>
    <p>密度兜底段落二：另一段同样超过二十五个字符的正文内容，用于验证段落合并逻辑。</p>
    <p>短</p>
    <p>版权所有 某某公司 ICP备12345号</p>
  </div>
</body></html>
"""

BODY_FALLBACK_HTML = (
    "<html><body><span>"
    + "正文兜底文本：这是一段没有任何段落标签包裹的长文本内容，用于触发 body 终极兜底路径。" * 6
    + "</span></body></html>"
)

BLOCKED_HTML = "<html><body><div>请登录后查看全文</div></body></html>"


@pytest.mark.parametrize(
    "html,expected",
    [
        (SIMPLE_HTML, ("第一段", "第二段")),
        (DENSITY_FALLBACK_HTML, ("密度兜底段落一", "密度兜底段落二")),
        (BODY_FALLBACK_HTML, ("正文兜底文本",)),
    ],
)
def test_extraction_result_matches_direct_parse(monkeypatch, html, expected):
    """限流是纯粹的调度改造：同一份 HTML 走完整入口与直接调解析函数结果必须一致。"""
    _patch_settings(monkeypatch)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: html)

    via_entry = crawl_and_extract_article("https://example.com/a")
    direct = _extract_article_text(html, url="https://example.com/a")

    assert via_entry == direct
    for token in expected:
        assert token in via_entry
    # 三条抽取路径的既有噪声过滤仍然生效
    assert "版权所有" not in via_entry
    assert "短" != via_entry


def _select_article_container_via_soupsieve(soup):
    """改造前的实现：逐个 select_one 扫全表，作为等价性对照基准。"""
    for selector in article_crawler.ARTICLE_CONTENT_SELECTORS:
        element = soup.select_one(selector)
        if element:
            text = element.get_text("\n").strip()
            if len(text) > 120:
                return selector, text
    return None, None


_LONG = "这是一段足够长的正文内容用于越过一百二十字符的长度闸门。" * 6
def _documents_for_selector_equivalence():
    """每条内置选择器都单独造一份文档，确保 24 条选择器全部被等价性断言覆盖。"""
    docs = []
    for selector in article_crawler.ARTICLE_CONTENT_SELECTORS:
        if selector.startswith("#"):
            docs.append(f"<html><body><div id='{selector[1:]}'>{_LONG}</div></body></html>")
        elif selector.startswith("."):
            classes = " ".join(selector[1:].split("."))
            docs.append(f"<html><body><div class='{classes}'>{_LONG}</div></body></html>")
        else:
            docs.append(f"<html><body><{selector}>{_LONG}</{selector}></body></html>")
    # 干扰场景：多选择器共存（优先级）、类名前缀相似、容器过短需继续往下找
    docs.append(
        "<html><body>"
        f"<div class='main-content'>{_LONG}</div>"
        f"<div class='rich-text'>{_LONG}RICH</div>"
        "</body></html>"
    )
    docs.append(
        "<html><body>"
        "<div class='common-width'>只有一个类，不该命中双类选择器</div>"
        f"<div class='common-width margin-bottom-20'>{_LONG}KR</div>"
        "</body></html>"
    )
    docs.append(f"<html><body><div class='article-content-extra'>{_LONG}</div></body></html>")
    docs.append(f"<html><body><div class='paywall'>短</div><div class='news_body'>{_LONG}</div></body></html>")
    docs.append("<html><body><p>没有任何正文容器</p></body></html>")
    docs.append(f"<html><body><div id='content'><div class='ArticleBody-articleBody'>{_LONG}</div></div></body></html>")
    return docs


@pytest.mark.parametrize("html", _documents_for_selector_equivalence())
def test_selector_index_matches_soupsieve_select_one(html):
    """单趟索引必须与逐个 select_one 给出完全相同的 (选择器, 正文)。

    这是把 24 次全树扫描（实测 550KB 页面上合计 ~457ms，解析阶段最大单项开销）
    换成一次索引遍历的等价性保证。
    """
    soup_fast = article_crawler.BeautifulSoup(html, article_crawler._BS4_PARSER)
    soup_ref = article_crawler.BeautifulSoup(html, article_crawler._BS4_PARSER)

    assert article_crawler.select_article_container(soup_fast) == (
        _select_article_container_via_soupsieve(soup_ref)
    )


def test_compiled_selector_table_covers_every_configured_selector():
    """所有内置选择器都应能被编译成简单选择器；新增复杂选择器时该断言会提醒作者。"""
    uncompiled = [sel for sel, compiled in article_crawler._COMPILED_CONTENT_SELECTORS if compiled is None]
    assert uncompiled == [], f"这些选择器会退回慢路径 select_one：{uncompiled}"


def test_unknown_complex_selector_falls_back_to_select_one(monkeypatch):
    """无法编译的复杂选择器仍走 soupsieve，不能被静默跳过。"""
    assert article_crawler._compile_simple_selector("a[href^='/detail/']") is None
    html = f"<html><body><section data-role='body'>{_LONG}</section></body></html>"
    monkeypatch.setattr(
        article_crawler,
        "_COMPILED_CONTENT_SELECTORS",
        (("section[data-role='body']", None),),
    )
    soup = article_crawler.BeautifulSoup(html, article_crawler._BS4_PARSER)
    selector, text = article_crawler.select_article_container(soup)
    assert selector == "section[data-role='body']"
    assert "这是一段足够长的正文内容" in text


def test_quality_gate_semantics_unchanged(monkeypatch):
    """质量闸门仍抛 ArticleQualityError（而不是被限流改写成 parse failed）。"""
    _patch_settings(monkeypatch)
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: BLOCKED_HTML)

    with pytest.raises(ArticleQualityError):
        crawl_and_extract_article("https://example.com/blocked")


def test_fetch_failure_semantics_unchanged(monkeypatch):
    """抓取失败仍是 RuntimeError('Webpage fetch failed: ...')，且不占用解析槽位。"""
    _patch_settings(monkeypatch, news_crawl_parse_concurrency=1)

    def boom(url, headers=None, timeout=None):
        raise TimeoutError("connect timeout")

    monkeypatch.setattr(article_crawler, "get_crawl_client", lambda: SimpleNamespace(get=boom))

    with pytest.raises(RuntimeError, match="Webpage fetch failed: TimeoutError"):
        crawl_and_extract_article("https://example.com/timeout")

    # 槽位未被占用：紧接着的正常抓取不应阻塞
    monkeypatch.setattr(article_crawler, "_fetch_article_html", lambda url, timeout: SIMPLE_HTML)
    assert "第一段" in crawl_and_extract_article("https://example.com/ok")
