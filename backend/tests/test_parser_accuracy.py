"""WS-4：抓取解析准确性与时效性回归测试。

覆盖的问题（每条都对应线上实测到的缺陷）：
  P0-1  财联社 HTML 选择器完全失效（产出 0 条）→ 改走官方 JSON 接口
  P0-2  选择器 HTML 的时间戳有 -24 小时错误（UTC 当天日期 + 硬编码 +08:00）
  P0-3  中文相对时间（刚刚 / N分钟前 / 昨天 HH:MM ...）完全无法解析 → published_at 全 NULL
  P1-1  Atom link 用 Element 真值判断 → alternate 分支永远失效
  P1-2  `_decode_response_html` 的"智能解码"对 httpx 是空操作 → GBK 页面全是乱码
  P1-3  正文兜底把登录墙/导航样板标成 success → 永久坏数据
  P1-4  抓取失败原因是空字符串 → 故障不可诊断
  额外  Zhipu 内联 JSON 因固定尾部标记 + 朴素反转义而整批解析失败
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from app.services.ingestion import utils as ingestion_utils
from app.services.ingestion.article_crawler import (
    ArticleQualityError,
    _decode_response_html,
    crawl_and_extract_article,
)
from app.services.ingestion.fetcher import (
    CLS_PARSER,
    CLS_REFERER,
    _classify_network_error,
    _describe_exception,
    build_cls_request,
    cls_sign,
    fetch_source_items,
)
from app.services.ingestion.parser import (
    _parse_cls_telegraph_json,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.types import SourceDefinition
from app.services.ingestion.utils import _parse_chinese_datetime, _parse_feed_datetime

FIXTURES = Path(__file__).parent / "fixtures"


def _cls_source(**overrides) -> SourceDefinition:
    params = dict(
        name="CLS Telegraph",
        source_type="html",
        url="https://www.cls.cn/v1/roll/get_roll_list",
        market="cn",
        language="zh",
        parser=CLS_PARSER,
        item_limit=20,
    )
    params.update(overrides)
    return SourceDefinition(**params)


# ---------------------------------------------------------------------------
# 1. 财联社官方 JSON 解析器（P0-1）
# ---------------------------------------------------------------------------


def test_cls_telegraph_json_parses_real_response_shape() -> None:
    payload = (FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8")

    items = _parse_cls_telegraph_json(payload, _cls_source())

    # 4 条中：id 为 null 的、非对象的两条被单条跳过，其余 3 条保留
    assert len(items) == 3

    first = items[0]
    assert first.title == "我国蜂群无人机首次实现台风过境全程立体观测"
    assert first.canonical_url == "https://www.cls.cn/detail/2437126"
    # ctime 是 epoch 秒，直接换算成 UTC
    assert first.published_at == datetime(2026, 7, 26, 4, 24, 15, tzinfo=UTC)
    assert "蜂群无人机" in (first.content_text or "")
    assert first.summary is not None and len(first.summary) <= 280


def test_cls_telegraph_json_falls_back_to_brief_when_title_empty() -> None:
    payload = (FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8")

    items = _parse_cls_telegraph_json(payload, _cls_source())

    second = items[1]
    assert second.canonical_url == "https://www.cls.cn/detail/2437127"
    # title 为空 → 回退到 brief 的【】标题
    assert second.title == "A股三大指数集体高开"
    assert second.published_at == datetime(2026, 7, 26, 4, 26, 40, tzinfo=UTC)


def test_cls_telegraph_json_keeps_item_when_timestamp_is_malformed() -> None:
    payload = (FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8")

    items = _parse_cls_telegraph_json(payload, _cls_source())

    last = items[-1]
    assert last.canonical_url == "https://www.cls.cn/detail/2437129"
    # ctime 是字符串、modified_time 是 null → published_at 降级为 None，条目本身保留
    assert last.published_at is None


def test_cls_telegraph_json_degrades_gracefully_on_business_error() -> None:
    payload = json.dumps({"errno": 5001, "msg": "sign error", "data": None})

    # errno != 0 不能让整批抓取抛异常
    assert _parse_cls_telegraph_json(payload, _cls_source()) == []


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps({"errno": 0, "msg": "", "data": {}}),
        json.dumps({"errno": 0, "msg": ""}),
        json.dumps({"errno": 0, "msg": "", "data": {"roll_data": None}}),
        json.dumps({"errno": 0, "msg": "", "data": {"roll_data": {}}}),
    ],
)
def test_cls_telegraph_json_missing_roll_data_returns_empty(payload: str) -> None:
    assert _parse_cls_telegraph_json(payload, _cls_source()) == []


def test_cls_telegraph_json_respects_item_limit_and_deduplicates() -> None:
    records = [
        {"id": 1, "title": "重复条目", "brief": "重复", "ctime": 1785039855},
        {"id": 1, "title": "重复条目", "brief": "重复", "ctime": 1785039855},
        {"id": 2, "title": "第二条", "brief": "第二条", "ctime": 1785039856},
        {"id": 3, "title": "第三条", "brief": "第三条", "ctime": 1785039857},
    ]
    payload = json.dumps({"errno": 0, "data": {"roll_data": records}}, ensure_ascii=False)

    items = _parse_cls_telegraph_json(payload, _cls_source(item_limit=2))

    assert [item.canonical_url for item in items] == [
        "https://www.cls.cn/detail/1",
        "https://www.cls.cn/detail/2",
    ]


# ---------------------------------------------------------------------------
# 2. 财联社签名与 Referer（P0-1）
# ---------------------------------------------------------------------------


def test_cls_sign_matches_sha1_then_md5_algorithm() -> None:
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "8.4.6",
        "rn": "20",
        "last_time": "",
        "category": "",
    }
    joined = "&".join(f"{key}={params[key]}" for key in sorted(params))
    expected = hashlib.md5(hashlib.sha1(joined.encode()).hexdigest().encode()).hexdigest()

    assert joined == "app=CailianpressWeb&category=&last_time=&os=web&rn=20&sv=8.4.6"
    assert cls_sign(params) == expected
    # 固定参数对应固定签名（实测该签名可从 cls.cn 取回 200 + 20 条真实快讯）
    assert cls_sign(params) == "a0911f4b64f95fa014607f21ddb7b0b2"


def test_build_cls_request_appends_sign_and_referer() -> None:
    url, headers = build_cls_request(_cls_source(item_limit=20))

    query = {key: value[0] for key, value in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}
    assert query["app"] == "CailianpressWeb"
    assert query["os"] == "web"
    assert query["rn"] == "20"
    assert query["sign"] == "a0911f4b64f95fa014607f21ddb7b0b2"
    assert headers["Referer"] == CLS_REFERER


def test_build_cls_request_keeps_endpoint_query_params_in_signature() -> None:
    source = _cls_source(url="https://www.cls.cn/v1/roll/get_roll_list?category=hongguan", item_limit=20)

    url, _ = build_cls_request(source)

    query = {key: value[0] for key, value in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}
    assert query["category"] == "hongguan"
    signed_params = {key: value for key, value in query.items() if key != "sign"}
    assert query["sign"] == cls_sign(signed_params)


def test_fetch_source_items_signs_cls_request_and_sends_referer(monkeypatch) -> None:
    payload = (FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8")
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        headers: dict = {}
        text = payload

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def get(self, url: str, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    outcome = fetch_source_items(_cls_source())

    assert outcome.error is None
    assert len(outcome.items) == 3
    assert captured["headers"]["Referer"] == CLS_REFERER
    query = parse_qs(urlsplit(captured["url"]).query, keep_blank_values=True)
    assert query["sign"] == ["a0911f4b64f95fa014607f21ddb7b0b2"]


# ---------------------------------------------------------------------------
# 3. -24 小时时间戳回归（P0-2）
# ---------------------------------------------------------------------------


def _selector_source(**overrides) -> SourceDefinition:
    params = dict(
        name="CLS Telegraph (selector)",
        source_type="html",
        url="https://www.cls.cn/telegraph",
        market="cn",
        parser="selector_html",
        entry_selector=".entry",
        title_selector=".c-34304b",
        link_selector="a[href^='/detail/']",
        time_selector=".telegraph-time-box",
        content_selector=".c-34304b",
    )
    params.update(overrides)
    return SourceDefinition(**params)


_SELECTOR_HTML_TEMPLATE = """
<div class="entry">
  <div class="telegraph-content-box">
    <span class="telegraph-time-box">{time_text}</span>
    <span class="c-34304b"><div>财联社测试内容</div></span>
  </div>
  <a href="/detail/123456">评论</a>
</div>
"""


def test_selector_html_midnight_beijing_does_not_shift_back_a_day(monkeypatch) -> None:
    """北京时间凌晨 1 点抓到的 01:00:12 快讯必须落在当天，而不是前一天。

    旧实现用 `_utc_now().date()`（UTC 还停在前一天）拼上硬编码的 `+08:00`，
    北京时间 00:00-08:00 的所有快讯 published_at 都整整早 24 小时。
    """
    # UTC 2026-07-24 17:00:30 == 北京时间 2026-07-25 01:00:30
    frozen_now = datetime(2026, 7, 24, 17, 0, 30, tzinfo=UTC)
    monkeypatch.setattr(ingestion_utils, "_utc_now", lambda: frozen_now)

    items = _parse_selector_html(
        _SELECTOR_HTML_TEMPLATE.format(time_text="01:00:12"), _selector_source()
    )

    assert len(items) == 1
    # 北京时间 2026-07-25 01:00:12 == UTC 2026-07-24 17:00:12
    assert items[0].published_at == datetime(2026, 7, 24, 17, 0, 12, tzinfo=UTC)


def test_selector_html_clock_far_in_future_rolls_back_one_day(monkeypatch) -> None:
    """北京时间刚过午夜时看到 23:50 的条目，说明它属于昨天。"""
    frozen_now = datetime(2026, 7, 24, 16, 30, tzinfo=UTC)  # 北京 2026-07-25 00:30
    monkeypatch.setattr(ingestion_utils, "_utc_now", lambda: frozen_now)

    items = _parse_selector_html(
        _SELECTOR_HTML_TEMPLATE.format(time_text="23:50:00"), _selector_source()
    )

    # 北京时间 2026-07-24 23:50 == UTC 2026-07-24 15:50
    assert items[0].published_at == datetime(2026, 7, 24, 15, 50, tzinfo=UTC)


def test_selector_html_uses_market_timezone_not_hardcoded_beijing(monkeypatch) -> None:
    """时区必须来自 source.market：美股源不能被当成北京时间。"""
    frozen_now = datetime(2026, 7, 24, 18, 0, tzinfo=UTC)  # 美东 2026-07-24 14:00 EDT
    monkeypatch.setattr(ingestion_utils, "_utc_now", lambda: frozen_now)

    items = _parse_selector_html(
        _SELECTOR_HTML_TEMPLATE.format(time_text="13:30:00"),
        _selector_source(market="us", url="https://example-us.test/live"),
    )

    # 美东 2026-07-24 13:30 EDT == UTC 17:30；若仍硬编码 +08:00 则会得到 05:30
    assert items[0].published_at == datetime(2026, 7, 24, 17, 30, tzinfo=UTC)


def test_selector_html_relative_chinese_time(monkeypatch) -> None:
    frozen_now = datetime(2026, 7, 25, 6, 30, tzinfo=UTC)  # 北京 14:30
    monkeypatch.setattr(ingestion_utils, "_utc_now", lambda: frozen_now)

    items = _parse_selector_html(
        _SELECTOR_HTML_TEMPLATE.format(time_text="5分钟前"), _selector_source()
    )

    assert items[0].published_at == datetime(2026, 7, 25, 6, 25, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 4. 中文相对/口语时间解析（P0-3）
# ---------------------------------------------------------------------------

# 参考时间：UTC 2026-07-25 06:30:00 == 北京时间 2026-07-25 14:30:00
_NOW = datetime(2026, 7, 25, 6, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("刚刚", datetime(2026, 7, 25, 6, 30, tzinfo=UTC)),
        ("刚才", datetime(2026, 7, 25, 6, 30, tzinfo=UTC)),
        ("30秒前", datetime(2026, 7, 25, 6, 29, 30, tzinfo=UTC)),
        ("5分钟前", datetime(2026, 7, 25, 6, 25, tzinfo=UTC)),
        ("5分前", datetime(2026, 7, 25, 6, 25, tzinfo=UTC)),
        ("3小时前", datetime(2026, 7, 25, 3, 30, tzinfo=UTC)),
        ("2天前", datetime(2026, 7, 23, 6, 30, tzinfo=UTC)),
        ("今天 14:30", datetime(2026, 7, 25, 6, 30, tzinfo=UTC)),
        ("昨天 09:15", datetime(2026, 7, 24, 1, 15, tzinfo=UTC)),
        ("前天 09:15", datetime(2026, 7, 23, 1, 15, tzinfo=UTC)),
        ("07-25 10:00", datetime(2026, 7, 25, 2, 0, tzinfo=UTC)),
        ("7月25日 10:00", datetime(2026, 7, 25, 2, 0, tzinfo=UTC)),
        ("2026-07-25 10:00:30", datetime(2026, 7, 25, 2, 0, 30, tzinfo=UTC)),
        ("2026年7月25日 10:00", datetime(2026, 7, 25, 2, 0, tzinfo=UTC)),
    ],
)
def test_parse_chinese_datetime_variants(text: str, expected: datetime) -> None:
    assert _parse_chinese_datetime(text, market="cn", now=_NOW) == expected


def test_parse_chinese_datetime_month_day_without_year_rolls_back_to_last_year() -> None:
    # 参考时间是 7 月；「12-31 08:00」只能是去年的条目
    parsed = _parse_chinese_datetime("12-31 08:00", market="cn", now=_NOW)

    assert parsed == datetime(2025, 12, 31, 0, 0, tzinfo=UTC)


def test_parse_chinese_datetime_returns_none_for_unrecognized_text() -> None:
    assert _parse_chinese_datetime("不是时间", market="cn", now=_NOW) is None
    assert _parse_chinese_datetime("", market="cn", now=_NOW) is None
    assert _parse_chinese_datetime(None, market="cn", now=_NOW) is None


def test_parse_feed_datetime_falls_back_to_chinese_relative_time() -> None:
    """接进 `_parse_feed_datetime` 的兜底链：36Kr 这类源不再全是 published_at=NULL。"""
    assert _parse_feed_datetime("5分钟前", market="cn", now=_NOW) == datetime(
        2026, 7, 25, 6, 25, tzinfo=UTC
    )
    assert _parse_feed_datetime("昨天 09:15", market="cn", now=_NOW) == datetime(
        2026, 7, 24, 1, 15, tzinfo=UTC
    )
    # 既有的 RFC2822 / ISO8601 行为不受影响
    assert _parse_feed_datetime("Mon, 17 Mar 2025 10:00:00 GMT") == datetime(
        2025, 3, 17, 10, 0, tzinfo=UTC
    )
    assert _parse_feed_datetime("2026-07-17T18:30:00", market="cn") == datetime(
        2026, 7, 17, 10, 30, tzinfo=UTC
    )


# ---------------------------------------------------------------------------
# 5. Atom link 选择（P1-1）
# ---------------------------------------------------------------------------


def test_atom_link_prefers_alternate_over_self() -> None:
    """`entry.find(...) or entry.find(...)` 对自闭合 <link/> 恒为 False。

    xml.etree 的 Element.__bool__ 判的是"有没有子元素"，于是 alternate 分支永远被吞掉，
    退化成"文档里第一个 link" —— 这个 fixture 把 self/edit 排在 alternate 之前，
    修复前会取到 .atom / /edit/ 地址。
    """
    xml = (FIXTURES / "us_atom_self_link_first.xml").read_text(encoding="utf-8")
    source = SourceDefinition(
        name="US Wire Atom",
        source_type="rss",
        url="https://example-us-wire.test/feed.atom",
        market="us",
        language="en",
    )

    items = _parse_rss_or_atom(xml, source)

    assert [item.canonical_url for item in items] == [
        "https://example-us-wire.test/story/fed-holds-rates-steady",
        "https://example-us-wire.test/story/chip-maker-raises-guidance",
    ]
    assert all(".atom" not in item.canonical_url for item in items)
    assert all("/edit/" not in item.canonical_url for item in items)


def test_atom_link_still_works_when_alternate_comes_first() -> None:
    """既有样本（alternate 排第一）行为不能变。"""
    xml = (FIXTURES / "us_atom_sample.xml").read_text(encoding="utf-8")
    source = SourceDefinition(
        name="US Wire Atom",
        source_type="rss",
        url="https://example-us-wire.test/feed.atom",
        market="us",
        language="en",
    )

    items = _parse_rss_or_atom(xml, source)

    assert items[0].canonical_url == "https://example-us-wire.test/story/regional-bank-earnings-beat"


# ---------------------------------------------------------------------------
# 6. 编码嗅探（P1-2）
# ---------------------------------------------------------------------------


class _FakeHttpxResponse:
    """模拟 httpx.Response：有 content/charset_encoding，没有 requests 的 apparent_encoding。"""

    def __init__(self, content: bytes, *, content_type: str = "text/html") -> None:
        self.content = content
        self.status_code = 200
        self.headers = {"Content-Type": content_type}
        # httpx 在响应头没有 charset 时，charset_encoding 是 None（但 .encoding 会返回 "utf-8"）
        self.charset_encoding = None
        self.encoding = "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        return None


_GBK_PAGE = (
    '<html><head><meta charset="gb2312"><title>东方财富</title></head>'
    "<body><div id=\"articleContent\"><p>沪深两市成交额突破一万亿元，北向资金净买入超过五十亿元。</p>"
    "<p>分析师认为，市场情绪明显回暖，后续仍需观察外围市场波动。</p></div></body></html>"
)


def test_decode_response_html_sniffs_meta_charset_for_gbk_page() -> None:
    response = _FakeHttpxResponse(_GBK_PAGE.encode("gb18030"))

    decoded = _decode_response_html(response)

    assert "�" not in decoded
    assert "沪深两市成交额突破一万亿元" in decoded


def test_decode_response_html_prefers_header_charset_over_meta() -> None:
    # 响应头声明 utf-8 而 meta 谎称 gb2312 → 以响应头为准
    page = '<html><head><meta charset="gb2312"></head><body>行情回暖</body></html>'
    response = _FakeHttpxResponse(page.encode("utf-8"), content_type="text/html; charset=utf-8")

    decoded = _decode_response_html(response)

    assert "行情回暖" in decoded
    assert "�" not in decoded


def test_decode_response_html_defaults_to_utf8_without_any_charset() -> None:
    page = "<html><body>没有任何 charset 声明</body></html>"
    response = _FakeHttpxResponse(page.encode("utf-8"))

    assert "没有任何 charset 声明" in _decode_response_html(response)


def test_crawl_and_extract_article_decodes_gbk_page(monkeypatch) -> None:
    response = _FakeHttpxResponse(_GBK_PAGE.encode("gb18030"))

    class FakeClient:
        def get(self, url: str, headers=None, timeout=None):
            return response

    monkeypatch.setattr(
        "app.services.ingestion.article_crawler.get_crawl_client", lambda: FakeClient()
    )

    content = crawl_and_extract_article("https://finance.example.cn/article/1")

    assert "�" not in content
    assert "沪深两市成交额突破一万亿元" in content


# ---------------------------------------------------------------------------
# 7. 正文质量闸门（P1-3）
# ---------------------------------------------------------------------------


def _crawl_html(monkeypatch, html: str) -> str:
    class FakeResponse:
        status_code = 200
        text = html
        content = None

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def get(self, url: str, headers=None, timeout=None):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.ingestion.article_crawler.get_crawl_client", lambda: FakeClient()
    )
    return crawl_and_extract_article("https://paywalled.example.com/story/1")


def test_login_wall_page_is_not_reported_as_success(monkeypatch) -> None:
    html = """
    <html><body>
      <div id="app">
        <div class="mask">请登录后查看全文，登录后可继续阅读本篇深度报道的剩余内容。</div>
      </div>
    </body></html>
    """

    with pytest.raises(ArticleQualityError):
        _crawl_html(monkeypatch, html)


def test_captcha_page_is_not_reported_as_success(monkeypatch) -> None:
    html = """
    <html><body>
      <div class="verify">安全验证：请输入验证码后继续访问本页面内容，以证明您不是自动化程序。</div>
    </body></html>
    """

    with pytest.raises(ArticleQualityError):
        _crawl_html(monkeypatch, html)


def test_navigation_boilerplate_body_fallback_is_rejected(monkeypatch) -> None:
    # 全部是短导航条目：既不满足密度兜底的 25 字门槛，也过不了 body 兜底的质量闸门
    nav_items = [
        "首页", "行情", "财经", "科技", "汽车", "房产", "体育", "娱乐",
        "登录", "注册", "关于我们", "联系我们", "隐私政策", "用户协议",
        "免责声明", "网站地图", "友情链接", "意见反馈", "下载APP", "关注我们",
    ]
    links = "".join(f"<span>{text}</span>" for text in nav_items)
    html = f"<html><body>{links}</body></html>"

    with pytest.raises(ArticleQualityError):
        _crawl_html(monkeypatch, html)


def test_js_shell_page_is_rejected(monkeypatch) -> None:
    html = '<html><body><div id="__next"></div></body></html>'

    with pytest.raises(ArticleQualityError):
        _crawl_html(monkeypatch, html)


def test_real_article_still_extracts_successfully(monkeypatch) -> None:
    """质量闸门不能误伤正常正文。"""
    body = (
        "美联储在最新一次议息会议上维持利率不变，声明中删除了对通胀持续回落的表述。"
        "市场普遍认为这意味着降息节奏可能放缓，美债收益率随即走高。"
        "多家投行在会后报告中调整了对明年利率路径的预期，认为首次降息时点可能推迟到下半年。"
    )
    html = f"<html><body><article><p>{body}</p></article></body></html>"

    content = _crawl_html(monkeypatch, html)

    assert "美联储在最新一次议息会议上维持利率不变" in content


def test_short_legit_body_fallback_still_succeeds(monkeypatch) -> None:
    """密度兜底保持宽松：短快讯正文（无拦截页特征）仍应成功。"""
    html = (
        "<html><body><article>"
        "<p>Detailed analysis of Apple's stock price movement and supply chain checks.</p>"
        "</article></body></html>"
    )

    content = _crawl_html(monkeypatch, html)

    assert "Detailed analysis" in content


# ---------------------------------------------------------------------------
# 8. 抓取失败原因不能是空串（P1-4）
# ---------------------------------------------------------------------------


class ReadTimeout(Exception):
    """模拟 httpx 超时类异常：str(exc) 是空串。"""

    def __str__(self) -> str:  # pragma: no cover - 行为由测试断言覆盖
        return ""


class ConnectError(Exception):
    def __str__(self) -> str:  # pragma: no cover - 行为由测试断言覆盖
        return ""


def test_describe_exception_keeps_type_name_when_message_empty() -> None:
    assert _describe_exception(ReadTimeout()) == "ReadTimeout"
    assert _describe_exception(ValueError("boom")) == "ValueError: boom"


def test_classify_network_error_splits_timeout_and_connect() -> None:
    assert _classify_network_error(ReadTimeout()) == "timeout"
    assert _classify_network_error(ConnectError()) == "connect_error"
    assert _classify_network_error(ValueError("other")) == "http_error"


def test_fetch_source_items_error_is_never_empty_string(monkeypatch) -> None:
    class FakeClient:
        def get(self, url: str, headers=None):
            raise ReadTimeout()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    outcome = fetch_source_items(
        SourceDefinition(
            name="Timeout Source",
            source_type="rss",
            url="https://example.com/feed.xml",
            market="us",
        )
    )

    assert outcome.error
    assert "ReadTimeout" in outcome.error
    assert outcome.error_kind == "timeout"


def test_fetch_source_items_http_status_error_carries_type_name(monkeypatch) -> None:
    class HTTPStatusError(Exception):
        def __str__(self) -> str:
            return ""

    class FakeResponse:
        status_code = 503
        headers: dict = {}
        text = ""

        def raise_for_status(self) -> None:
            raise HTTPStatusError()

    class FakeClient:
        def get(self, url: str, headers=None):
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    outcome = fetch_source_items(
        SourceDefinition(
            name="Broken Source",
            source_type="rss",
            url="https://example.com/feed.xml",
            market="us",
        )
    )

    assert outcome.error == "HTTPStatusError"
    assert outcome.error_kind == "http_error"


def test_fetch_source_items_does_not_retry_on_internal_type_error(monkeypatch) -> None:
    """P2：只有"客户端不接受 headers 关键字"时才允许降级重发，不能吞掉内部 TypeError。"""
    calls: list[tuple] = []

    class FakeClient:
        def get(self, url: str, headers=None):
            calls.append((url, headers))
            raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    outcome = fetch_source_items(
        SourceDefinition(
            name="Internal TypeError Source",
            source_type="rss",
            url="https://example.com/feed.xml",
            market="us",
        )
    )

    # 只请求一次（旧实现会静默重发第二次不带条件头的请求）
    assert len(calls) == 1
    assert outcome.error is not None
    assert "TypeError" in outcome.error


def test_fetch_source_items_still_falls_back_for_clients_without_headers_kwarg(monkeypatch) -> None:
    calls: list[str] = []

    class FakeResponse:
        status_code = 200
        headers: dict = {}
        text = "<rss version='2.0'><channel></channel></rss>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def get(self, url: str):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    outcome = fetch_source_items(
        SourceDefinition(
            name="Legacy Fake Client Source",
            source_type="rss",
            url="https://example.com/feed.xml",
            market="us",
        )
    )

    assert outcome.error is None
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# 9. Zhipu 内联 JSON：括号配平 + JSON 语义反转义
# ---------------------------------------------------------------------------


def _zhipu_source() -> SourceDefinition:
    return SourceDefinition(
        name="Zhipu AI News",
        source_type="html",
        url="https://www.zhipuai.cn/zh/news",
        market="cn",
        language="zh",
        parser="zhipu_news_inline_json",
    )


_ZHIPU_RECORDS = [
    {
        "id": 152,
        "title_zh": "智谱首份业绩报告发布，探索AGI智能上界",
        "title_en": "Z.ai 2025 Annual Results",
        "createAt": "2026-03-31T10:00:00.000Z",
        "category": "news",
        "resume_zh": '发布会上 CEO 表示："我们把 AGI 的 \\"上界\\" 又推高了一点。"',
        "resume_en": None,
        # 正文块里再嵌一层富文本结构，模拟真实的 RSC 载荷深度
        "content_zh": {
            "root": {
                "children": [
                    {
                        "type": "text",
                        "text": '同时 AutoGLM 启动大规模百万内测，官方称其为 "面向 C 端用户的产品"。',
                        "format": 0,
                        "detail": 0,
                        "mode": "normal",
                        "style": "",
                    }
                ]
            }
        },
    },
    {
        "id": 151,
        "title_zh": "智谱（02513.HK）公布2025年度业绩发布会安排",
        "title_en": None,
        "createAt": "2026-03-30T04:00:00.000Z",
        "resume_zh": "业绩发布会将于香港时间上午十点举行。",
        "resume_en": None,
    },
    # 单条降级样本：字段畸形只跳过该条
    {"id": None, "title_zh": "缺少 id", "createAt": "2026-03-29T04:00:00.000Z"},
    "这不是一个对象",
    {"id": 150, "title_zh": "", "title_en": "", "createAt": "2026-03-28T04:00:00.000Z"},
]


def _build_zhipu_next_html(*, trailing_locale_marker: bool) -> str:
    """构造 Next.js RSC 风格页面：JSON 被当作 JSON 字符串字面量嵌在 push 调用里。"""
    inner_json = json.dumps({"newsItems": _ZHIPU_RECORDS}, ensure_ascii=False)
    # 去掉最外层大括号，模拟 newsItems 只是某个大对象里的一个字段
    chunk = '3:["$","$L10",null,{' + inner_json[1:-1] + ',"locale":"zh"}]\n'
    pushes = [
        'self.__next_f.push([1,' + json.dumps("2:I[1234,[],\"\"]\n", ensure_ascii=False) + ']);',
        'self.__next_f.push([1,' + json.dumps(chunk, ensure_ascii=False) + ']);',
    ]
    if trailing_locale_marker:
        # 页面后半段还有一个"看起来很像尾部标记"的片段，旧实现会误命中它，
        # 把数组一路吃到几十万字符之外。
        decoy = '4:["$","$L11",null,{"footerItems":[{"id":1}],"locale":"zh"}]\n'
        pushes.append('self.__next_f.push([1,' + json.dumps(decoy, ensure_ascii=False) + ']);')
    return "<html><body><script>" + "".join(pushes) + "</script></body></html>"


def _legacy_naive_parse(content: str) -> list:
    """复刻修复前的实现：固定尾部标记 + 朴素 str.replace 反转义。"""
    start_marker = 'newsItems\\":['
    start_index = content.find(start_marker)
    if start_index == -1:
        start_index = content.find("newsItems")
    array_start = content.find("[", start_index)
    array_end = content.find('],\\"locale\\":', array_start)
    raw_array = content[array_start : array_end + 1] if array_end != -1 else content[array_start:]
    normalized = raw_array.replace('\\"', '"').replace("\\/", "/")
    return json.loads(normalized)


def test_zhipu_legacy_naive_unescape_fails_on_nested_escapes() -> None:
    """修复前的朴素 replace 方案在嵌套转义的正文上必然崩。"""
    html = _build_zhipu_next_html(trailing_locale_marker=True)

    with pytest.raises((json.JSONDecodeError, ValueError)):
        _legacy_naive_parse(html)


@pytest.mark.parametrize("trailing_locale_marker", [True, False])
def test_zhipu_parses_nested_escaped_rsc_payload(trailing_locale_marker: bool) -> None:
    """括号配平定位 + JSON 语义反转义：有无尾部标记都能正确解析。"""
    html = _build_zhipu_next_html(trailing_locale_marker=trailing_locale_marker)

    items = _parse_zhipu_news_inline_json(html, _zhipu_source())

    # 5 条记录里：id 为 None、非对象、标题全空的三条被单条跳过
    assert len(items) == 2
    assert items[0].title == "智谱首份业绩报告发布，探索AGI智能上界"
    assert items[0].canonical_url == "https://www.zhipuai.cn/zh/news/152"
    assert items[0].published_at == datetime(2026, 3, 31, 10, 0, tzinfo=UTC)
    assert "上界" in (items[0].summary or "")
    assert items[1].canonical_url == "https://www.zhipuai.cn/zh/news/151"


def test_zhipu_plain_inline_json_still_parses() -> None:
    """既有的简单内联 JSON 页面（无 RSC 转义）行为不变。"""
    html = """
    <script>
      self.__next_f.push([1,"anything"]);
      "newsItems":[{"id":97,"title_zh":"智谱新闻标题","title_en":null,
      "createAt":"2025-08-25T06:56:41.718Z","resume_zh":"智谱新闻摘要","resume_en":null}]
    </script>
    """

    items = _parse_zhipu_news_inline_json(html, _zhipu_source())

    assert len(items) == 1
    assert items[0].title == "智谱新闻标题"
    assert items[0].canonical_url == "https://www.zhipuai.cn/zh/news/97"
    assert items[0].summary == "智谱新闻摘要"


def test_zhipu_missing_payload_raises() -> None:
    with pytest.raises(ValueError):
        _parse_zhipu_news_inline_json("<html><body>no payload here</body></html>", _zhipu_source())
