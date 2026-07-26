"""WS-5：去重、相关性闸门与信息源扩容的回归测试。

覆盖：
1. 中文宏观/政策快讯的相关性闸门回归（修复前这些用例全部失败）；
2. 中文娱乐/体育/天气噪声仍被拒；
3. has_official_signal 词边界（"Sector Watch" / "Federated News" 不再绕过闸门）；
4. published_at 为 None 时的兜底判重；
5. 灰区数字/日期差异否决（金融数据快讯靠数字区分，不能交给 embedding 判重）；
6. prime 宽窗口保护（陈旧条目混入不得触发全表加载）；
7. simhash 记忆化（重复比较时 sha256 计算次数不线性增长）；
8. 标题截断与签名一致性；
9. sources.py：CLS 切到官方 JSON parser，且全部源定义合法。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.ingestion.dedup_gate import (
    MAX_PRIME_WINDOW,
    TITLE_SIGNATURE_MAX_LENGTH,
    DuplicateGate,
    _signature_from_parts,
    normalize_url_for_hash,
)
from app.services.ingestion.sources import _default_sources, _validate_source_definition
from app.services.ingestion.types import SourceItem
from app.services.news_dedup import (
    numbers_contradict,
    set_secondary_judge,
    simhash64,
    titles_look_duplicate,
)
from app.services.news_priority import (
    evaluate_ingest_relevance_gate,
    has_official_signal,
    passes_ingest_relevance_gate,
)

# —— 1. 中文相关性回归 ——

# 线上实证：Wallstreetcn Live 抓 330 次只入库 5 条、CLS Telegraph 入库 0 条，
# 根因就是这一类中文快讯被闸门全量误杀（英文分词对纯中文标题产出空 token 集）。
CHINESE_MACRO_FLASHES = [
    ("央行下调存款准备金率0.5个百分点", "货币政策：降准/存款准备金率"),
    ("美联储宣布降息25个基点", "货币政策：降息/美联储"),
    ("国家统计局：11月CPI同比上涨0.2%", "宏观数据：CPI/国家统计局/同比上涨"),
    ("证监会发布上市公司监管新规", "监管机构：证监会/上市公司/监管新规"),
    ("商务部对原产于美国的商品加征关税", "贸易：商务部/加征关税"),
    ("OPEC+宣布减产", "商品：OPEC/减产"),
]


def test_chinese_macro_flashes_pass_ingest_gate() -> None:
    failures = [
        f"{title}（应命中 {category}）"
        for title, category in CHINESE_MACRO_FLASHES
        if not passes_ingest_relevance_gate(title=title, source_name="CLS Telegraph")
    ]
    assert not failures, "以下中文快讯被闸门误杀：" + "; ".join(failures)


def test_chinese_macro_flashes_report_strong_reason() -> None:
    """放行理由必须是强信号，不能靠 concept_mover 这类弱理由蒙混过关。"""
    for title, _category in CHINESE_MACRO_FLASHES:
        decision = evaluate_ingest_relevance_gate(title=title, source_name="Some Blog")
        assert decision.passed is True, title
        assert decision.reason.startswith("market_signal:"), (title, decision.reason)


def test_more_chinese_market_flashes_pass_gate() -> None:
    for title in [
        "人民币中间价大幅调升",
        "国务院常务会议部署稳外贸措施，扩大出口信用保险",  # 供应链/进出口类
        "美国商务部将多家中国企业列入实体清单",
        "沪指涨1.2%，两市成交额突破1.5万亿元",
        "某公司发布业绩预告，预计净利润同比增长80%",
        "OPEC+维持减产协议不变，国际原油上涨",
    ]:
        assert passes_ingest_relevance_gate(title=title, source_name="Wallstreetcn Live") is True, title


# —— 2. 中文负面样本 ——


def test_chinese_noise_samples_still_rejected() -> None:
    noise_samples = [
        ("某明星演唱会门票秒罄，粉丝直呼太难抢", "娱乐"),
        ("中超联赛第20轮：主队3比1夺冠，球员赛后落泪", "体育"),
        ("明日北京天气预报：气温骤降并伴有暴雨", "天气"),
        ("周末去哪儿玩？这份旅游攻略请收好", "生活"),
    ]
    for title, category in noise_samples:
        decision = evaluate_ingest_relevance_gate(title=title, source_name="36Kr")
        assert decision.passed is False, f"{category} 噪声不应放行：{title}"


def test_weak_chinese_concept_mover_still_rejected() -> None:
    """"概念+涨停" 仍是弱信号，不得因为中文词表扩容而被顺带放行。"""
    decision = evaluate_ingest_relevance_gate(
        title="某概念股涨停，市场热议",
        summary="题材炒作跟涨",
        source_name="WeChat Hot Takes",
    )
    assert decision.passed is False
    assert decision.reason.startswith("weak_signal:")


# —— 3. has_official_signal 词边界 ——


def test_official_signal_uses_word_boundary_for_short_hints() -> None:
    # 修复前：源名含 "sec"/"fed"/"boe" 子串就整源绕过闸门。
    assert has_official_signal("Sector Watch") is False
    assert has_official_signal("Secondary Market Daily") is False
    assert has_official_signal("Federated News") is False
    assert has_official_signal("Fedora Weekly") is False


def test_official_signal_still_recognizes_real_official_sources() -> None:
    assert has_official_signal("SEC Press Releases") is True
    assert has_official_signal("SEC EDGAR 8-K") is True
    assert has_official_signal("sec.gov newsroom") is True
    assert has_official_signal("US-SEC Filings") is True
    assert has_official_signal("Company IR Portal") is True
    assert has_official_signal("Boeing IR") is True
    assert has_official_signal("港交所公告") is True
    # 央行源靠 "federal reserve" 这类长提示词命中（"Federal" 不再被 "fed" 子串误命中，
    # 所以必须显式收录完整名称）。
    assert has_official_signal("Federal Reserve Press Releases") is True


def test_lookalike_source_no_longer_bypasses_gate() -> None:
    """"Sector Watch" 这类源不再享受官方源豁免，弱文本必须被拒。"""
    decision = evaluate_ingest_relevance_gate(
        title="Hands-on smartphone camera review for gaming laptops",
        summary="Benchmark battery and display impressions",
        source_name="Sector Watch",
    )
    assert decision.passed is False
    assert decision.reason != "official_source"


# —— 4/6/8. DuplicateGate ——


class _FakeSession:
    """只实现 DuplicateGate 需要的 execute/get 的最小 session。"""

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows
        self.executed_windows: list[tuple[datetime, datetime]] = []
        self.execute_calls = 0

    def execute(self, statement):
        self.execute_calls += 1
        # 从编译后的字面量参数里取窗口边界，用于断言"窗口没有被撑到全表"。
        params = statement.compile(compile_kwargs={"literal_binds": False}).params
        bounds = sorted(value for value in params.values() if isinstance(value, datetime))
        if len(bounds) >= 2:
            self.executed_windows.append((bounds[0], bounds[-1]))
        window_start, window_end = (bounds[0], bounds[-1]) if len(bounds) >= 2 else (None, None)

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if window_start is None:
            return _Result(list(self._rows))
        return _Result(
            [row for row in self._rows if window_start <= row[3] <= window_end]
        )

    def get(self, _model, news_id):
        return news_id


def _item(title: str, url: str, published_at: datetime | None) -> SourceItem:
    return SourceItem(
        title=title,
        canonical_url=url,
        summary=None,
        content_text=None,
        published_at=published_at,
    )


def test_null_published_items_still_deduplicate_within_batch() -> None:
    """P1：published_at 为空的新闻此前 100% 不参与去重（36Kr/MiniMax 全是 NULL）。"""
    now = datetime.now(UTC)
    session = _FakeSession(
        [(11, "月之暗面发布 Kimi K3 模型并开放 API", "https://36kr.com/newsflashes/1", now)]
    )
    gate = DuplicateGate(session)
    gate.prime([_item("月之暗面发布 Kimi K3 模型并开放 API", "https://36kr.com/newsflashes/2", None)])

    duplicate = gate.find_duplicate(
        _item("月之暗面发布 Kimi K3 模型并开放 API", "https://36kr.com/newsflashes/2", None)
    )

    assert duplicate == 11


def test_null_published_item_outside_window_is_not_duplicate() -> None:
    now = datetime.now(UTC)
    stale = now - timedelta(days=3)
    session = _FakeSession([(11, "月之暗面发布 Kimi K3 模型并开放 API", "https://36kr.com/a", stale)])
    gate = DuplicateGate(session)
    incoming = _item("月之暗面发布 Kimi K3 模型并开放 API", "https://36kr.com/b", None)
    gate.prime([incoming])

    assert gate.find_duplicate(incoming) is None


def test_prime_skips_full_table_load_when_batch_window_is_too_wide() -> None:
    """P1-3：批内混入一条陈旧条目不得让 prime 拉取跨年区间的所有 news_item。"""
    now = datetime.now(UTC)
    session = _FakeSession([])
    gate = DuplicateGate(session)

    gate.prime(
        [
            _item("fresh headline about revenue guidance", "https://a.com/1", now),
            # MarketPulse 实测存在 published 停留在 2024-10 的条目
            _item("stale headline about revenue guidance", "https://a.com/2", now - timedelta(days=400)),
        ]
    )

    # 宽窗口下直接放弃预取，不发那条会加载整个表的范围查询。
    assert gate.last_prime_skipped_reason == "window_too_wide"
    assert gate._candidates is None
    assert session.execute_calls == 0

    # 随后的逐条判重仍然只查各自的 ±60 分钟小窗口。
    gate.find_duplicate(_item("fresh headline about revenue guidance", "https://a.com/1", now))
    assert session.execute_calls == 1
    window_start, window_end = session.executed_windows[0]
    assert window_end - window_start <= MAX_PRIME_WINDOW


def test_prime_still_uses_index_for_narrow_batches() -> None:
    now = datetime.now(UTC)
    session = _FakeSession([])
    gate = DuplicateGate(session)
    gate.prime(
        [
            _item("headline one about revenue guidance", "https://a.com/1", now),
            _item("headline two about revenue guidance", "https://a.com/2", now - timedelta(minutes=30)),
        ]
    )

    assert gate.last_prime_skipped_reason is None
    assert gate._candidates is not None
    assert session.execute_calls == 1
    # 预取过后逐条判重不再发查询。
    gate.find_duplicate(_item("headline one about revenue guidance", "https://a.com/1", now))
    assert session.execute_calls == 1


def test_signature_matches_between_truncated_and_untruncated_title() -> None:
    """P2-2：入库写的是 title[:500]，签名必须也按截断后的标题算，否则漏杀。"""
    long_title = "央行下调存款准备金率" * 80  # 800 字，远超 500
    stored_title = long_title[:TITLE_SIGNATURE_MAX_LENGTH]

    assert len(long_title) > TITLE_SIGNATURE_MAX_LENGTH
    assert _signature_from_parts(long_title, "https://cls.cn/detail/1") == _signature_from_parts(
        stored_title, "https://cls.cn/detail/1"
    )


def test_signature_ignores_host_mirrors() -> None:
    base = _signature_from_parts("Fed signals rate cut in July", "https://example.com/a")
    for mirror in ("https://www.example.com/a", "https://m.example.com/a", "https://amp.example.com/a"):
        assert _signature_from_parts("Fed signals rate cut in July", mirror) == base


# —— P1-2 URL 归一化 ——


def test_normalize_url_strips_tracking_params_only() -> None:
    assert (
        normalize_url_for_hash("https://Example.com/news/a?utm_source=wire&utm_medium=rss#top")
        == "https://example.com/news/a"
    )
    assert normalize_url_for_hash("https://example.com/news/a?spm=1.2.3&from=timeline") == "https://example.com/news/a"
    # 文章 id 在 query 里时不能被剥掉
    assert normalize_url_for_hash("https://example.com/detail?id=123&utm_source=x") == (
        "https://example.com/detail?id=123"
    )
    # 末尾斜杠与默认端口归一
    assert normalize_url_for_hash("https://example.com:443/news/") == "https://example.com/news"


def test_normalize_url_is_noop_for_plain_urls() -> None:
    for url in ["https://news.example.com/story-1", "http://feeds.marketwatch.com/marketwatch/bulletins/"]:
        normalized = normalize_url_for_hash(url)
        assert normalized.startswith(("http://", "https://"))
    assert normalize_url_for_hash("https://news.example.com/story-1") == "https://news.example.com/story-1"


# —— 5. 灰区数字差异否决 ——


class _AlwaysDuplicateJudge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def is_duplicate(self, title_a: str, title_b: str) -> bool | None:
        self.calls.append((title_a, title_b))
        return True


NUMERIC_LOOKALIKE_PAIRS = [
    ("国家统计局：11月CPI同比上涨0.2%", "国家统计局：11月CPI同比上涨0.6%"),
    ("美国上周初请失业金人数21.9万人", "美国上周初请失业金人数23.9万人"),
    ("比亚迪11月销量50.68万辆", "比亚迪10月销量50.68万辆"),
]


def test_numeric_difference_vetoes_gray_zone_duplicate() -> None:
    """P2-3：只差一个数字/月份的金融数据快讯不得被 embedding 判官判成重复。"""
    judge = _AlwaysDuplicateJudge()
    set_secondary_judge(judge)
    try:
        for left, right in NUMERIC_LOOKALIKE_PAIRS:
            assert titles_look_duplicate(left, right) is False, (left, right)
    finally:
        from app.services.news_dedup import NullSecondaryDuplicateJudge

        set_secondary_judge(NullSecondaryDuplicateJudge())

    assert judge.calls == [], "数字矛盾的标题不应再询问二次判官"


def test_numbers_contradict_helper() -> None:
    assert numbers_contradict("CPI 上涨 0.2%", "CPI 上涨 0.6%") is True
    assert numbers_contradict("11月销量创新高", "10月销量创新高") is True
    assert numbers_contradict("CPI 上涨 0.2%", "CPI 上涨 0.2%") is False
    assert numbers_contradict("Fed signals rate cut", "Fed signals rate cut soon") is False
    # 千分位不应被当成差异
    assert numbers_contradict("下跌1,250元/吨", "下跌1250元/吨") is False


def test_gray_zone_still_consults_judge_when_numbers_match() -> None:
    judge = _AlwaysDuplicateJudge()
    set_secondary_judge(judge)
    try:
        # 无数字、措辞略有差异的标题仍走二次判官（是否落灰区由 simhash 决定，
        # 这里只断言"没有被数字否决直接短路"）。
        titles_look_duplicate(
            "Fed officials signal a rate cut could come in July meeting",
            "Fed officials signalled a rate cut may come at the July meeting",
        )
    finally:
        from app.services.news_dedup import NullSecondaryDuplicateJudge

        set_secondary_judge(NullSecondaryDuplicateJudge())
    assert numbers_contradict(
        "Fed officials signal a rate cut could come in July meeting",
        "Fed officials signalled a rate cut may come at the July meeting",
    ) is False


# —— 7. simhash 记忆化 ——


@dataclass
class _Sha256Counter:
    calls: int = 0


def test_simhash_is_memoized_per_title(monkeypatch) -> None:
    """P1-3：同一标题反复比较时 sha256 次数不得线性增长。"""
    import app.services.news_dedup as dedup

    counter = _Sha256Counter()
    real_sha256 = dedup.sha256

    def counting_sha256(data):
        counter.calls += 1
        return real_sha256(data)

    monkeypatch.setattr(dedup, "sha256", counting_sha256)
    simhash64.cache_clear()

    title_a = "Nvidia supplier lifts AI server guidance for the second half"
    title_b = "Apple unveils a brand new iPhone lineup at its autumn event"

    titles_look_duplicate(title_a, title_b)
    after_first = counter.calls
    assert after_first > 0

    for _ in range(20):
        titles_look_duplicate(title_a, title_b)

    assert counter.calls == after_first, "重复比较同一对标题不应再触发任何 sha256 计算"
    simhash64.cache_clear()


# —— 9. sources.py ——


def test_cls_telegraph_uses_official_json_api() -> None:
    source = {item.name: item for item in _default_sources()}["CLS Telegraph"]

    assert source.url == "https://www.cls.cn/v1/roll/get_roll_list"
    assert source.parser == "cls_telegraph_json"
    assert source.source_type == "html"
    assert source.cadence_seconds == 100
    # 失效的 CSS 选择器必须全部清掉
    assert source.entry_selector is None
    assert source.title_selector is None
    assert source.link_selector is None
    assert source.time_selector is None
    assert source.content_selector is None


def test_all_default_sources_remain_valid_and_unique() -> None:
    sources = _default_sources()
    names = [source.name for source in sources]

    assert len(names) == len(set(names)), f"重复源名：{names}"
    for source in sources:
        _validate_source_definition(source)
        assert source.url.startswith(("http://", "https://")), source.name


def test_flash_tier_cadence_and_expanded_sources_present() -> None:
    by_name = {source.name: source for source in _default_sources()}

    # 快讯层 100s，其余 300s
    for name in ("CLS Telegraph", "Wallstreetcn Live", "MarketWatch MarketPulse"):
        assert by_name[name].cadence_seconds == 100, name
    for name, source in by_name.items():
        if name not in {"CLS Telegraph", "Wallstreetcn Live", "MarketWatch MarketPulse"}:
            assert source.cadence_seconds == 300, name

    # WS-5 实测通过的扩容源
    for name in (
        "Federal Reserve Press Releases",
        "SEC Speeches and Statements",
        "CNBC Economy",
        "CNBC Earnings",
        "Seeking Alpha Market Currents",
        "MarketWatch Bulletins",
        "Investing.com Economy",
        "Investing.com Stock Market",
        "Eastmoney Finance",
        "36Kr Newsflash",
    ):
        assert name in by_name, f"缺少扩容源：{name}"
        assert by_name[name].source_type == "rss", name
