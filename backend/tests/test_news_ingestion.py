import json
import os
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.source_health import SourceHealth
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.news import NewsItemSummary
from app.services.news_ingestion import (
    NewsIngestionService,
    RefreshSummary,
    SourceDefinition,
    SourceItem,
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_wallstreetcn_live_json,
    _parse_zhipu_news_inline_json,
    load_sources,
)


def _load_sources_from_config(config_path, monkeypatch):
    original_news_sources_file = os.environ.get("NEWS_SOURCES_FILE")
    monkeypatch.setenv("NEWS_SOURCES_FILE", str(config_path))
    get_settings.cache_clear()
    try:
        return load_sources()
    finally:
        if original_news_sources_file is None:
            monkeypatch.delenv("NEWS_SOURCES_FILE", raising=False)
        else:
            monkeypatch.setenv("NEWS_SOURCES_FILE", original_news_sources_file)
        get_settings.cache_clear()


def test_parse_rss_source_items() -> None:
    xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title>Example headline</title>
          <link>https://example.com/story</link>
          <description><![CDATA[<p>Summary text</p>]]></description>
          <pubDate>Mon, 17 Mar 2025 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    source = SourceDefinition(name="Example", source_type="rss", url="https://example.com/feed", market="us")

    items = _parse_rss_or_atom(xml, source)

    assert len(items) == 1
    assert items[0].title == "Example headline"
    assert items[0].canonical_url == "https://example.com/story"
    assert items[0].summary == "Summary text"
    assert items[0].published_at == datetime(2025, 3, 17, 10, 0, tzinfo=UTC)


def test_parse_rss_dc_date_when_pubdate_missing() -> None:
    xml = """
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <title>DC date headline</title>
          <link>https://example.com/dc-date</link>
          <dc:date>2026-07-17T18:30:00+08:00</dc:date>
        </item>
      </channel>
    </rss>
    """
    source = SourceDefinition(name="CN Feed", source_type="rss", url="https://example.com/feed", market="cn")

    items = _parse_rss_or_atom(xml, source)

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 7, 17, 10, 30, tzinfo=UTC)


def test_parse_feed_datetime_naive_iso_as_asia_shanghai() -> None:
    from app.services.ingestion.utils import _parse_feed_datetime

    parsed = _parse_feed_datetime("2026-07-17T18:30:00", market="cn")

    assert parsed == datetime(2026, 7, 17, 10, 30, tzinfo=UTC)


def test_parse_feed_datetime_naive_iso_us_market_uses_eastern() -> None:
    from app.services.ingestion.utils import _parse_feed_datetime

    # 2026-07-17 EDT = UTC-4
    parsed = _parse_feed_datetime("2026-07-17T18:30:00", market="us")

    assert parsed == datetime(2026, 7, 17, 22, 30, tzinfo=UTC)


def test_parse_selector_html_source_items() -> None:
    html = """
    <div class="entry">
      <div class="telegraph-content-box">
        <span class="telegraph-time-box">15:03:13</span>
        <span class="c-34304b"><div>财联社测试内容</div></span>
      </div>
      <a href="/detail/123456">评论</a>
    </div>
    """
    source = SourceDefinition(
        name="CLS Telegraph",
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

    items = _parse_selector_html(html, source)

    assert len(items) == 1
    assert items[0].title == "财联社测试内容"
    assert items[0].canonical_url == "https://www.cls.cn/detail/123456"
    assert items[0].content_text == "财联社测试内容"


def test_parse_anchor_list_html_deduplicates_links() -> None:
    html = """
    <div>
      <a href="/news/minimax-m2">MiniMax M2</a>
      <a href="/news/minimax-m2">MiniMax M2</a>
      <a href="/news/minimax-m21">MiniMax M2.1</a>
    </div>
    """
    source = SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
        entry_selector="a[href^='/news/']",
    )

    items = _parse_anchor_list_html(html, source)

    assert len(items) == 2
    assert items[0].canonical_url == "https://www.minimaxi.com/news/minimax-m2"


def test_parse_minimax_detail_html_extracts_date_and_body() -> None:
    html = r"""
    <html>
      <head>
        <title>Music 2.5+: 解锁纯音乐，突破风格边界 - MiniMax News | MiniMax</title>
      </head>
      <body>
        <script>
          self.__next_f.push([1,"6:[[\"$\",\"$L17\",null,{\"data\":{\"base_resp\":{\"status_code\":0},\"title\":\"Music 2.5+: 解锁纯音乐，突破风格边界\",\"content\":[{\"id\":\"article-title\",\"type\":\"ArticleTitle\",\"props\":{\"date\":\"2026-03-04\",\"title\":\"Music 2.5+: 解锁纯音乐，突破风格边界\"},\"children\":[]},{\"id\":\"article-paragraph\",\"type\":\"ArticleParagraph\",\"props\":{\"content\":\"$18\"},\"children\":[]}],\"slug\":\"music-25-解锁纯音乐突破风格边界\"}}]]"]);
        </script>
        <script>
          self.__next_f.push([1,"\u003cdiv style=\"max-width: 768px;\"\u003e
          \u003cp\u003e今天，我们介绍MiniMax Music 2.5正式上线纯音乐创作能力。\u003c/p\u003e
          \u003cp\u003e欢迎使用 MiniMax Music 2.5+，解锁你的音乐创造力！\u003c/p\u003e
          \u003c/div\u003e"]);
        </script>
      </body>
    </html>
    """
    source = SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
    )

    item = _parse_minimax_detail_html(
        html,
        source,
        canonical_url="https://www.minimaxi.com/news/music-25-解锁纯音乐突破风格边界",
        fallback_title="MiniMax Music 2.5+",
    )

    assert item.title == "Music 2.5+: 解锁纯音乐，突破风格边界"
    assert item.published_at == datetime(2026, 3, 4, 0, 0, tzinfo=UTC)
    assert "今天，我们介绍MiniMax Music 2.5正式上线纯音乐创作能力。" in item.content_text
    assert item.summary == "今天，我们介绍MiniMax Music 2.5正式上线纯音乐创作能力。 欢迎使用 MiniMax Music 2.5+，解锁你的音乐创造力！"


def test_parse_zhipu_inline_json_source_items() -> None:
    html = """
    <script>
      self.__next_f.push([1,"anything"]);
      "newsItems":[{"id":97,"title_zh":"智谱新闻标题","title_en":null,"createAt":"2025-08-25T06:56:41.718Z","resume_zh":"智谱新闻摘要","resume_en":null}]
    </script>
    """
    source = SourceDefinition(
        name="Zhipu AI News",
        source_type="html",
        url="https://www.zhipuai.cn/zh/news",
        market="cn",
        parser="zhipu_news_inline_json",
    )

    items = _parse_zhipu_news_inline_json(html, source)

    assert len(items) == 1
    assert items[0].title == "智谱新闻标题"
    assert items[0].canonical_url == "https://www.zhipuai.cn/zh/news/97"
    assert items[0].summary == "智谱新闻摘要"


def test_parse_wallstreetcn_live_json_uses_title_when_present() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {
                        "id": 3777927,
                        "uri": "https://wallstreetcn.com/articles/3777927",
                        "title": "特朗普宣布再次竞选总统",
                        "content": "<p>正文 html</p>",
                        "content_text": "正文纯文本",
                        "display_time": 1700000000,
                    }
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].title == "特朗普宣布再次竞选总统"
    assert items[0].canonical_url == "https://wallstreetcn.com/articles/3777927"
    assert items[0].content_text == "正文纯文本"
    assert items[0].content_html == "<p>正文 html</p>"
    assert items[0].published_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_parse_wallstreetcn_live_json_falls_back_to_content_text_when_title_missing() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {
                        "id": 3139744,
                        "uri": "https://wallstreetcn.com/livenews/3139744",
                        "title": "",
                        "content": "<p>沙特主导的联盟继续实施军事行动。</p>",
                        "content_text": "沙特主导的联盟继续实施军事行动，袭击也门胡塞武装的供应和军事场所，多国紧急谴责此次行动导致地区局势进一步升级紧张。（也门电视台快讯）",
                        "display_time": 1721900000,
                    }
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].title == "沙特主导的联盟继续实施军事行动，袭击也门胡塞武装的供应和军事场所，多国紧急谴责此次行动导致地区局势进一步升级紧张。（也门"
    assert len(items[0].title) == 60
    assert items[0].published_at == datetime(2024, 7, 25, 9, 33, 20, tzinfo=UTC)


def test_parse_wallstreetcn_live_json_skips_records_missing_id_or_uri() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {"id": None, "uri": "https://wallstreetcn.com/livenews/1", "title": "缺 id", "content_text": "x"},
                    {"id": 2, "uri": None, "title": "缺 uri", "content_text": "x"},
                    {"id": 3, "uri": "https://wallstreetcn.com/livenews/3", "title": "", "content_text": ""},
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert items == []


def test_parse_wallstreetcn_live_json_handles_non_string_uri_and_title() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {"id": 1, "uri": 12345, "title": "非字符串 uri", "content_text": "x"},
                    {
                        "id": 2,
                        "uri": "https://wallstreetcn.com/livenews/2",
                        "title": ["非字符串标题"],
                        "content_text": "正文兜底内容",
                    },
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].canonical_url == "https://wallstreetcn.com/livenews/2"
    assert items[0].title == "正文兜底内容"


def test_parse_wallstreetcn_live_json_out_of_range_display_time_keeps_record() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {
                        "id": 1,
                        "uri": "https://wallstreetcn.com/livenews/1",
                        "title": "时间戳超出范围",
                        "content_text": "x",
                        "display_time": 99999999999999999,
                    }
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].title == "时间戳超出范围"
    assert items[0].published_at is None


def test_load_sources_caches_registry_until_mtime_changes(tmp_path, monkeypatch) -> None:
    """news_sources_file 的 (mtime, size) 未变时命中进程内缓存,变化后重读。"""
    from app.services.ingestion.sources import clear_sources_cache

    # 两个名称等长,保证重写后文件大小不变,可单独控制 mtime 变量。
    def _payload(name: str) -> str:
        return json.dumps(
            {
                "sources": [
                    {
                        "name": name,
                        "source_type": "rss",
                        "url": "https://example.com/cached-feed.xml",
                        "market": "us",
                    }
                ]
            }
        )

    config = tmp_path / "sources.json"
    config.write_text(_payload("Cached Feed Alpha"), encoding="utf-8")
    original_stat = config.stat()

    monkeypatch.setenv("NEWS_SOURCES_FILE", str(config))
    get_settings.cache_clear()
    clear_sources_cache()
    try:
        first = load_sources()
        assert any(item.name == "Cached Feed Alpha" for item in first)

        # 同大小重写 + 还原 mtime:内容已变但 (mtime, size) 未变 → 命中缓存,不重读。
        config.write_text(_payload("Cached Feed Omega"), encoding="utf-8")
        os.utime(config, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        second = load_sources()
        assert any(item.name == "Cached Feed Alpha" for item in second)
        assert not any(item.name == "Cached Feed Omega" for item in second)

        # mtime 前进 → 缓存失效,重新读取文件内容。
        os.utime(config, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000_000))
        third = load_sources()
        assert any(item.name == "Cached Feed Omega" for item in third)

        # clear_sources_cache 后即使签名不变也强制重读。
        clear_sources_cache()
        fourth = load_sources()
        assert any(item.name == "Cached Feed Omega" for item in fourth)
    finally:
        clear_sources_cache()
        get_settings.cache_clear()


def test_load_sources_backfills_registry_defaults_from_legacy_config(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Legacy Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = _load_sources_from_config(config, monkeypatch)

    legacy = next(item for item in sources if item.name == "Legacy Feed")
    assert legacy.tier == "primary"
    assert legacy.priority == 100
    assert legacy.cadence_seconds == 300
    assert legacy.markets == ["us"]
    assert legacy.supports_incremental is False


def test_load_sources_accepts_api_source_registry_entries(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "The News API",
                        "source_type": "api",
                        "url": "https://api.thenewsapi.com/v1/news/top",
                        "market": "us",
                        "language": "en",
                        "tier": "secondary",
                        "parser": "the_news_api_json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = _load_sources_from_config(config, monkeypatch)

    api_source = next(item for item in sources if item.name == "The News API")
    assert api_source.source_type == "api"
    assert api_source.parser == "the_news_api_json"
    assert api_source.tier == "secondary"


def test_load_sources_rejects_invalid_tier(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        "tier": "broken",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid tier"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_invalid_priority(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        "priority": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="priority must be positive"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_invalid_cadence_seconds(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        "cadence_seconds": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cadence_seconds must be positive"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_malformed_registry_entries(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({"sources": [1]}), encoding="utf-8")

    with pytest.raises(ValueError, match="source definition at index 0 must be an object"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_null_sources_array(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({"sources": None}), encoding="utf-8")

    with pytest.raises(ValueError, match="sources must be an array"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_non_numeric_priority(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        "priority": "high",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="priority must be a number"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_non_numeric_cadence_seconds(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        "cadence_seconds": "often",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cadence_seconds must be a number"):
        _load_sources_from_config(config, monkeypatch)


def test_load_sources_rejects_malformed_markets_array(tmp_path, monkeypatch) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "markets": {"us": True},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="markets must be an array of strings"):
        _load_sources_from_config(config, monkeypatch)


@pytest.mark.parametrize("payload", [None, []])
def test_load_sources_rejects_malformed_top_level_payload(tmp_path, monkeypatch, payload) -> None:
    config = tmp_path / "sources.json"
    config.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sources registry payload must be an object"):
        _load_sources_from_config(config, monkeypatch)


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        ("priority", float("inf"), "priority must be a finite number"),
        ("cadence_seconds", float("nan"), "cadence_seconds must be a finite number"),
    ],
)
def test_load_sources_rejects_non_finite_registry_values(
    tmp_path, monkeypatch, field_name, field_value, message
) -> None:
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Broken Feed",
                        "source_type": "rss",
                        "url": "https://example.com/rss",
                        "market": "us",
                        field_name: field_value,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        _load_sources_from_config(config, monkeypatch)


def test_refresh_source_tracks_health_per_source_market_pair(monkeypatch) -> None:
    class FakeResponse:
        text = "<rss version='2.0'><channel></channel></rss>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    source_name = "Multi Market Feed"
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    try:
        with SessionLocal() as session:
            service = NewsIngestionService(session)
            service._refresh_source(
                SourceDefinition(
                    name=source_name,
                    source_type="rss",
                    url="https://example.com/us/rss",
                    market="us",
                    markets=["us", "hk"],
                )
            )
            service._refresh_source(
                SourceDefinition(
                    name=source_name,
                    source_type="rss",
                    url="https://example.com/hk/rss",
                    market="hk",
                    markets=["us", "hk"],
                )
            )

            health_rows = SourceHealthRepository(session).list_all()
            scoped_rows = [item for item in health_rows if item.source_name == source_name]
            assert {(item.source_name, item.market) for item in scoped_rows} == {
                (source_name, "us"),
                (source_name, "hk"),
            }
    finally:
        with SessionLocal() as session:
            session.execute(delete(SourceHealth).where(SourceHealth.source_name == source_name))
            session.commit()


def test_initialize_database_prefers_news_item_market_when_backfilling_source_health(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE source_health")
        connection.exec_driver_sql(
            """
            CREATE TABLE source_health (
                id INTEGER PRIMARY KEY,
                source_name VARCHAR(120) NOT NULL UNIQUE,
                source_type VARCHAR(16) NOT NULL,
                last_success_at DATETIME,
                last_failure_at DATETIME,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                total_fetches INTEGER NOT NULL DEFAULT 0,
                total_failures INTEGER NOT NULL DEFAULT 0,
                avg_latency_ms FLOAT,
                is_disabled BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO source_health (
                source_name,
                source_type,
                consecutive_failures,
                total_fetches,
                total_failures,
                is_disabled
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Legacy Feed", "rss", 2, 5, 1, 0),
        )

    with testing_session() as session:
        session.add(
            NewsItem(
                source_name="Legacy Feed",
                source_url="https://example.com/rss",
                title="Legacy title",
                summary=None,
                canonical_url="https://example.com/legacy",
                url_hash="legacy-hash",
                market="hk",
                language=None,
                sentiment_label=None,
                sentiment_score=None,
                published_at=None,
                fetched_at=datetime(2026, 3, 25, 10, 0, tzinfo=UTC),
                ingest_status="ingested",
            )
        )
        session.commit()

    # The legacy database has tables but no alembic_version, so
    # initialize_database baselines it and runs `alembic upgrade head`,
    # which executes the source_health market backfill migration.
    # Alembic (env.py) resolves the database from settings, so point it
    # at the temporary legacy database; disable demo seeding as this
    # test only cares about the schema repair.
    test_settings = Settings(database_url=f"sqlite:///{db_path}", seed_demo_data=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.db.initializer.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.db.initializer.engine", engine)
    monkeypatch.setattr(
        "app.services.news_ingestion.load_sources",
        lambda: [
            SourceDefinition(
                name="Legacy Feed",
                source_type="rss",
                url="https://example.com/rss",
                market="us",
                markets=["us", "hk"],
            )
        ],
    )

    initialize_database()

    with testing_session() as session:
        row = session.scalar(select(SourceHealth).where(SourceHealth.source_name == "Legacy Feed"))
        assert row is not None
        assert row.market == "hk"
        assert row.consecutive_failures == 2
        assert row.total_fetches == 5
        assert row.total_failures == 1


def test_persist_item_backfills_existing_news_when_detail_arrives() -> None:
    source = SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
    )
    canonical_url = "https://www.minimaxi.com/news/test-backfill"
    url_hash = sha256(canonical_url.encode("utf-8")).hexdigest()

    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.add(
            NewsItem(
                source_name=source.name,
                source_url=source.url,
                title="MiniMax Backfill",
                summary=None,
                canonical_url=canonical_url,
                url_hash=url_hash,
                market="hk",
                language="zh",
                sentiment_label=None,
                sentiment_score=None,
                published_at=None,
                fetched_at=datetime(2026, 3, 17, 8, 0, tzinfo=UTC),
                ingest_status="ingested",
            )
        )
        session.commit()

    try:
        with SessionLocal() as session:
            service = NewsIngestionService(session)
            service._persist_item(
                source,
                SourceItem(
                    title="MiniMax Backfill",
                    canonical_url=canonical_url,
                    summary="正文摘要",
                    content_text="正文摘要 正文内容",
                    content_html="<p>正文摘要</p><p>正文内容</p>",
                    published_at=datetime(2026, 3, 17, 7, 30, tzinfo=UTC),
                    extract_status="success",
                ),
            )
            session.commit()

            stored = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
            article = session.scalar(select(ArticleContent).where(ArticleContent.news_id == stored.id))

            assert stored is not None
            assert stored.published_at == datetime(2026, 3, 17, 7, 30)
            assert stored.summary == "正文摘要"
            assert article is not None
            assert article.extract_status == "success"
            assert article.content_text == "正文摘要 正文内容"
    finally:
        with SessionLocal() as session:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
            session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
            session.commit()


def test_refresh_source_supports_api_news_payload(monkeypatch) -> None:
    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "Nvidia supplier sees AI server demand accelerate",
                        "description": "The company raised guidance after stronger AI server orders.",
                        "snippet": "AI server demand remains strong heading into the second half.",
                        "url": "https://news.example.com/story-1",
                        "published_at": "2026-03-26T01:00:00Z",
                    }
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="The News API",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="us",
        language="en",
        tier="secondary",
        parser="the_news_api_json",
    )

    inserted_url = "https://news.example.com/story-1"
    url_hash = sha256(inserted_url.encode("utf-8")).hexdigest()
    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()

    try:
        with SessionLocal() as session:
            result = NewsIngestionService(session)._refresh_source(source)

            stored = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
            article = session.scalar(select(ArticleContent).where(ArticleContent.news_id == stored.id))

            assert result.status == "ok"
            assert result.fetched_count == 1
            assert result.inserted_count == 1
            assert stored is not None
            assert stored.source_name == "The News API"
            assert stored.summary == "The company raised guidance after stronger AI server orders."
            assert article is not None
            assert article.content_text == "AI server demand remains strong heading into the second half."
    finally:
        with SessionLocal() as session:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
            session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
            session.commit()


def test_refresh_source_skips_same_window_duplicate_titles_from_same_host(monkeypatch) -> None:
    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "Nvidia supplier lifts AI server guidance",
                        "description": "Headline rewrite one.",
                        "snippet": "Body one.",
                        "url": "https://news.example.com/story-1",
                        "published_at": "2026-03-26T01:00:00Z",
                    },
                    {
                        "uuid": "story-2",
                        "title": "NVIDIA supplier lifts AI server guidance!",
                        "description": "Headline rewrite two.",
                        "snippet": "Body two.",
                        "url": "https://news.example.com/story-2?utm_source=wire",
                        "published_at": "2026-03-26T01:20:00Z",
                    },
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="The News API",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="us",
        language="en",
        tier="secondary",
        parser="the_news_api_json",
    )
    url_hashes = [
        sha256(b"https://news.example.com/story-1").hexdigest(),
        sha256(b"https://news.example.com/story-2?utm_source=wire").hexdigest(),
    ]
    with SessionLocal() as session:
        session.execute(
            delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
        )
        session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
        session.commit()

    try:
        with SessionLocal() as session:
            result = NewsIngestionService(session)._refresh_source(source)
            stored_items = session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))).all()

            assert result.status == "ok"
            assert result.fetched_count == 2
            assert result.inserted_count == 1
            assert len(stored_items) == 1
    finally:
        with SessionLocal() as session:
            session.execute(
                delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
            )
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()


def test_refresh_source_promotes_duplicate_to_primary_source_metadata(monkeypatch) -> None:
    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "TSMC raises advanced packaging expansion plan",
                        "description": "Secondary rewrite first.",
                        "snippet": "Secondary rewrite body.",
                        "url": "https://news.example.com/story-1",
                        "published_at": "2026-03-26T02:00:00Z",
                    }
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    primary_source = SourceDefinition(
        name="HKEX",
        source_type="api",
        url="https://api.hkex.example.com/news",
        market="hk",
        language="zh",
        tier="primary",
        parser="the_news_api_json",
    )
    secondary_source = SourceDefinition(
        name="The News API",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="us",
        language="en",
        tier="secondary",
        parser="the_news_api_json",
    )
    inserted_url = "https://news.example.com/story-1"
    url_hash = sha256(inserted_url.encode("utf-8")).hexdigest()
    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()

    try:
        with SessionLocal() as session:
            service = NewsIngestionService(session)
            service._refresh_source(secondary_source)
            service._refresh_source(primary_source)

            stored = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))

            assert stored is not None
            assert stored.source_name == "HKEX"
            assert stored.source_url == primary_source.url
            assert stored.market == "hk"
    finally:
        with SessionLocal() as session:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
            session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
            session.commit()


def test_refresh_source_deduplicates_same_window_chinese_titles(monkeypatch) -> None:
    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "台积电上调资本开支",
                        "description": "中文改写一。",
                        "snippet": "中文正文一。",
                        "url": "https://news.example.com/cn-story-1",
                        "published_at": "2026-03-26T03:00:00Z",
                    },
                    {
                        "uuid": "story-2",
                        "title": "台积电上调资本开支！",
                        "description": "中文改写二。",
                        "snippet": "中文正文二。",
                        "url": "https://news.example.com/cn-story-2",
                        "published_at": "2026-03-26T03:10:00Z",
                    },
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="The News API CN",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="hk",
        language="zh",
        tier="secondary",
        parser="the_news_api_json",
    )
    url_hashes = [
        sha256(b"https://news.example.com/cn-story-1").hexdigest(),
        sha256(b"https://news.example.com/cn-story-2").hexdigest(),
    ]
    with SessionLocal() as session:
        session.execute(
            delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
        )
        session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
        session.commit()

    try:
        with SessionLocal() as session:
            result = NewsIngestionService(session)._refresh_source(source)
            stored_items = session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))).all()

            assert result.status == "ok"
            assert result.inserted_count == 1
            assert len(stored_items) == 1
    finally:
        with SessionLocal() as session:
            session.execute(
                delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
            )
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()


def test_refresh_news_endpoint_returns_summary(monkeypatch) -> None:
    class FakeIngestionService:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self) -> RefreshSummary:
            now = datetime(2025, 3, 17, 10, 0, tzinfo=UTC)
            from app.services.news_ingestion import SourceFetchResult

            return RefreshSummary(
                started_at=now,
                finished_at=now,
                fetched_count=10,
                inserted_count=4,
                results=[
                    SourceFetchResult(
                        source_name="The Verge",
                        source_type="rss",
                        status="ok",
                        fetched_count=5,
                        inserted_count=2,
                        error=None,
                        latency_ms=123.4,
                    )
                ],
            )

    monkeypatch.setattr("app.api.routes.news.NewsIngestionService", FakeIngestionService)

    client = TestClient(app)
    response = client.post("/api/news/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fetched_count"] == 10
    assert payload["inserted_count"] == 4
    assert payload["results"][0]["source_name"] == "The Verge"


def test_refresh_news_endpoint_notifies_exact_inserted_items(monkeypatch) -> None:
    inserted_item = NewsItem(
        id=999,
        source_name="Inserted Source",
        source_url="https://example.com/feed",
        title="Inserted news",
        summary="Inserted summary",
        canonical_url="https://example.com/inserted",
        url_hash="inserted-hash",
        market="us",
        language="en",
        sentiment_label=None,
        sentiment_score=None,
        published_at=datetime(2025, 3, 17, 9, 0, tzinfo=UTC),
        fetched_at=datetime(2025, 3, 17, 9, 1, tzinfo=UTC),
        effective_at=datetime(2025, 3, 17, 9, 0, tzinfo=UTC),
        ingest_status="ingested",
    )

    class FakeNotificationService:
        def __init__(self) -> None:
            self.news_payloads: list[dict] = []

        def on_news_created_batch(self, payloads: list[dict]) -> None:
            self.news_payloads.extend(payloads)

    class FakeNewsRepository:
        def __init__(self, session) -> None:
            self.session = session

        def get_by_id(self, news_id: int):
            assert news_id == 999
            return inserted_item

        def get_by_ids(self, news_ids: list[int]):
            return [inserted_item for nid in news_ids if nid == 999]

    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    from app import main as main_module
    from app.workers.queue_worker import BackgroundQueueWorker, analysis_queue

    while not analysis_queue.empty():
        try:
            analysis_queue.get_nowait()
        except Exception:
            break

    notification_service = FakeNotificationService()
    fake_bus = FakeBus()
    monkeypatch.setattr(main_module, "build_event_bus", lambda: fake_bus)
    monkeypatch.setattr(main_module, "NewsRepository", FakeNewsRepository)
    monkeypatch.setattr(main_module, "get_notification_service", lambda: notification_service)
    monkeypatch.setattr("app.workers.queue_worker.get_notification_service", lambda: notification_service)

    class FakePipelineService:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session
            self.session_factory = session_factory
        def process_news_ids(self, news_ids: list[int]):
            return type("Summary", (), {"news_ids": list(news_ids), "processed_count": len(news_ids)})()

    monkeypatch.setattr("app.workers.queue_worker.NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr("app.workers.queue_worker.NewsRepository", FakeNewsRepository)

    class DummySession:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def commit(self): pass
        def close(self): pass
        def add(self, instance): pass
        def execute(self, *args, **kwargs):
            class DummyResult:
                def scalars(self):
                    return type("Scalar", (), {"all": lambda: [], "first": lambda: None})()
            return DummyResult()
        def scalar(self, *args, **kwargs):
            return None

    main_module._register_event_handlers()
    fake_bus.publish("news.created_batch", {"news_ids": [999]})

    qw = BackgroundQueueWorker(session_factory=lambda: DummySession())
    monkeypatch.setattr(qw, "_record_success", lambda *args, **kwargs: None)
    qw.run_cycle()

    assert notification_service.news_payloads == [
        {
            "title": "Inserted news",
            "summary": "Inserted summary",
            "source_name": "Inserted Source",
            "market": "us",
            "published_at": "2025-03-17T09:00:00+00:00",
        }
    ]


def test_refresh_all_publishes_news_created_for_each_insert(monkeypatch) -> None:
    source = SourceDefinition(
        name="Pipeline Refresh",
        source_type="rss",
        url="https://example.com/pipeline-feed",
        market="us",
        language="en",
    )
    feed = """
    <rss version="2.0">
      <channel>
        <item>
          <title>NVIDIA raises revenue guidance on AI demand</title>
          <link>https://example.com/pipeline-refresh-item</link>
          <description>Chipmaker lifts outlook for data-center GPUs</description>
          <pubDate>Wed, 19 Mar 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    url_hash = sha256(b"https://example.com/pipeline-refresh-item").hexdigest()

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str) -> FakeResponse:
            assert url == source.url
            return FakeResponse(feed)

    calls: list[list[int]] = []

    class FakeEventBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}
            self.published: list[tuple[str, dict[str, object]]] = []

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    bus = FakeEventBus()
    bus.subscribe("news.created_batch", lambda payload: calls.append(payload["news_ids"]))

    monkeypatch.setattr("app.services.news_ingestion.load_sources", lambda: [source])
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    monkeypatch.setattr("app.services.news_ingestion.get_event_bus", lambda: bus)

    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()

        summary = NewsIngestionService(session).refresh_all()

        assert summary.inserted_count == 1
        assert len(summary.inserted_items) == 1
        inserted_id = summary.inserted_items[0].id
        inserted_payload = NewsItemSummary.model_validate(summary.inserted_items[0], from_attributes=True).model_dump(mode="json")
        assert bus.published == [
            (
                "news.created",
                {
                    "id": inserted_id,
                    "title": "NVIDIA raises revenue guidance on AI demand",
                    "summary": "Chipmaker lifts outlook for data-center GPUs",
                    "source_name": "Pipeline Refresh",
                    "canonical_url": "https://example.com/pipeline-refresh-item",
                    "market": "us",
                    "sentiment_label": None,
                    "editorial_score": None,
                    "ai_takeaway": None,
                    "published_at": "2026-03-19T10:00:00Z",
                    "fetched_at": inserted_payload["fetched_at"],
                    "effective_at": inserted_payload["effective_at"],
                },
            ),
            ("news.created_batch", {"news_ids": [inserted_id]}),
        ]
        assert calls == [[inserted_id]]

        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()


def test_refresh_all_does_not_process_pending_when_no_new_items(monkeypatch) -> None:
    source = SourceDefinition(
        name="Pipeline Backfill",
        source_type="rss",
        url="https://example.com/pipeline-backfill-feed",
        market="us",
        language="en",
    )
    existing_url = "https://example.com/pipeline-existing-item"
    url_hash = sha256(existing_url.encode("utf-8")).hexdigest()
    feed = f"""
    <rss version="2.0">
      <channel>
        <item>
          <title>Already known item</title>
          <link>{existing_url}</link>
          <description>Repeated item</description>
          <pubDate>Wed, 19 Mar 2026 11:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str) -> FakeResponse:
            assert url == source.url
            return FakeResponse(feed)

    calls: list[list[int]] = []

    class FakePipelineService:
        def __init__(self, session) -> None:
            self.session = session

        def list_pending_news_ids(self, *, limit: int) -> list[int]:
            del limit
            return [pending.id]

        def process_news_ids(self, news_ids: list[int]) -> None:
            calls.append(news_ids)

    monkeypatch.setattr("app.services.news_ingestion.load_sources", lambda: [source])
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    monkeypatch.setattr("app.services.news_ingestion.NewsSignalPipelineService", FakePipelineService)

    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        pending = NewsItem(
            source_name="Pipeline Backfill",
            source_url=source.url,
            title="Already known item",
            summary="Repeated item",
            canonical_url=existing_url,
            url_hash=url_hash,
            market="us",
            language="en",
            sentiment_label=None,
            sentiment_score=None,
            signal_status=None,
            signal_error=None,
            signal_updated_at=None,
            published_at=datetime(2026, 3, 19, 11, 0, tzinfo=UTC),
            fetched_at=datetime(2026, 3, 19, 11, 1, tzinfo=UTC),
            ingest_status="ingested",
        )
        session.add(pending)
        session.commit()

        summary = NewsIngestionService(session).refresh_all()

        assert summary.inserted_count == 0
        # pending 由 BackgroundQueueWorker 单入口处理,refresh_all 不再就地消费
        assert calls == []

        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()


def test_refresh_all_hydrates_minimax_details_in_fetch_phase(monkeypatch) -> None:
    """MiniMax 详情水合在并发抓取阶段完成:refresh_all 落库的记录带 published_at/正文。"""
    from app.services.ingestion.detail_hydration import minimax_detail_cooldown

    source = SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
        entry_selector="a[href^='/news/']",
        item_limit=20,
    )
    detail_url = "https://www.minimaxi.com/news/refresh-hydration-test"
    feed = '<html><body><a href="/news/refresh-hydration-test">MiniMax revenue surges on AI chip demand</a></body></html>'
    detail_html = r"""
    <html>
      <head><title>MiniMax revenue surges on AI chip demand - MiniMax News | MiniMax</title></head>
      <body>
        <script>
          self.__next_f.push([1,"6:[[\"$\",\"$L17\",null,{\"data\":{\"base_resp\":{\"status_code\":0},\"title\":\"MiniMax revenue surges on AI chip demand\",\"content\":[{\"id\":\"article-title\",\"type\":\"ArticleTitle\",\"props\":{\"date\":\"2026-03-04\",\"title\":\"MiniMax revenue surges on AI chip demand\"},\"children\":[]}],\"slug\":\"refresh-hydration-test\"}}]]"]);
        </script>
        <script>
          self.__next_f.push([1,"\u003cdiv style=\"max-width: 768px;\"\u003e
          \u003cp\u003eMiniMax reported record revenue as AI chip demand lifted guidance.\u003c/p\u003e
          \u003c/div\u003e"]);
        </script>
      </body>
    </html>
    """

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    requested: list[str] = []

    class FakeClient:
        def get(self, url: str, headers=None) -> FakeResponse:
            requested.append(url)
            if url == source.url:
                return FakeResponse(feed)
            return FakeResponse(detail_html)

    class FakeEventBus:
        def __init__(self) -> None:
            self.published: list[tuple[str, dict[str, object]]] = []

        def subscribe(self, event_name: str, handler) -> None:
            return None

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))

    monkeypatch.setattr("app.services.news_ingestion.load_sources", lambda: [source])
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    monkeypatch.setattr("app.services.news_ingestion.get_event_bus", lambda: FakeEventBus())
    minimax_detail_cooldown.clear()

    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.canonical_url == detail_url))))
        session.execute(delete(NewsItem).where(NewsItem.canonical_url == detail_url))
        session.commit()

        try:
            summary = NewsIngestionService(session).refresh_all()

            assert summary.inserted_count == 1
            assert detail_url in requested

            stored = session.scalar(select(NewsItem).where(NewsItem.canonical_url == detail_url))
            article = session.scalar(select(ArticleContent).where(ArticleContent.news_id == stored.id))
            assert stored is not None
            assert stored.published_at == datetime(2026, 3, 4, 0, 0)
            assert article is not None
            assert article.extract_status == "success"
            assert "record revenue" in (article.content_text or "")
        finally:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.canonical_url == detail_url))))
            session.execute(delete(NewsItem).where(NewsItem.canonical_url == detail_url))
            session.commit()


def test_news_created_batch_subscriber_publishes_news_signals_processed(monkeypatch) -> None:
    from app import main as main_module

    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}
            self.published: list[tuple[str, dict[str, object]]] = []

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    class FakePipelineService:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session
            self.session_factory = session_factory

        def process_news_ids(self, news_ids: list[int]):
            return type("Summary", (), {"news_ids": list(news_ids), "processed_count": len(news_ids)})()

    from datetime import datetime
    from typing import Any

    from app.workers.queue_worker import BackgroundQueueWorker, analysis_queue

    while not analysis_queue.empty():
        try:
            analysis_queue.get_nowait()
        except Exception:
            break

    class FakeNewsItem:
        def __init__(self, item_id: int):
            self.id = item_id
            self.title = "title"
            self.summary = "summary"
            self.source_name = "source"
            self.canonical_url = f"https://example.com/{item_id}"
            self.market = "us"
            self.sentiment_label = None
            self.editorial_score = None
            self.ai_takeaway = None
            self.published_at = datetime(2025, 3, 17, 9, 0, tzinfo=UTC)
            self.fetched_at = datetime(2025, 3, 17, 9, 1, tzinfo=UTC)
            self.effective_at = datetime(2025, 3, 17, 9, 0, tzinfo=UTC)

    class FakeNewsRepositoryForProcessed:
        def __init__(self, session) -> None:
            self.session = session
        def get_by_ids(self, news_ids: list[int]) -> list[Any]:
            return [FakeNewsItem(nid) for nid in news_ids]

    class FakeNotificationService:
        def on_news_created_batch(self, payloads: list[dict]) -> None: pass

    fake_bus = FakeBus()
    monkeypatch.setattr(main_module, "build_event_bus", lambda: fake_bus)
    monkeypatch.setattr(main_module, "NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr("app.workers.queue_worker.NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr("app.workers.queue_worker.NewsRepository", FakeNewsRepositoryForProcessed)
    monkeypatch.setattr(main_module, "get_notification_service", lambda: FakeNotificationService())

    class DummySession:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def commit(self): pass
        def close(self): pass
        def execute(self, *args, **kwargs):
            class DummyResult:
                def scalars(self):
                    return type("Scalar", (), {"all": lambda: [], "first": lambda: None})()
            return DummyResult()
        def scalar(self, *args, **kwargs):
            return None

    main_module._register_event_handlers()
    fake_bus.publish("news.created_batch", {"news_ids": [11, 12]})

    qw = BackgroundQueueWorker(session_factory=lambda: DummySession())
    monkeypatch.setattr(qw, "_record_success", lambda *args, **kwargs: None)
    qw.run_cycle()

    assert ("news.signals_processed", {"news_ids": [11, 12], "processed_count": 2}) in fake_bus.published


def test_refresh_source_deduplicates_across_hour_boundary(monkeypatch) -> None:
    """23:58 与 00:02 跨自然小时的同题新闻必须判重(滑动窗口修复回归)。"""

    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "Fed signals rate cut in July",
                        "description": "Wire one.",
                        "snippet": "Body one.",
                        "url": "https://news.example.com/boundary-1",
                        "published_at": "2026-03-26T01:58:00Z",
                    },
                    {
                        "uuid": "story-2",
                        "title": "Fed signals rate cut in July.",
                        "description": "Wire two.",
                        "snippet": "Body two.",
                        "url": "https://news.example.com/boundary-2",
                        "published_at": "2026-03-26T02:02:00Z",
                    },
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="The News API",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="us",
        language="en",
        tier="secondary",
        parser="the_news_api_json",
    )
    url_hashes = [
        sha256(b"https://news.example.com/boundary-1").hexdigest(),
        sha256(b"https://news.example.com/boundary-2").hexdigest(),
    ]

    def _cleanup() -> None:
        with SessionLocal() as session:
            session.execute(
                delete(ArticleContent).where(
                    ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes)))
                )
            )
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()

    _cleanup()
    try:
        with SessionLocal() as session:
            result = NewsIngestionService(session)._refresh_source(source)
            stored_items = session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))).all()

            assert result.status == "ok"
            assert result.fetched_count == 2
            assert result.inserted_count == 1
            assert len(stored_items) == 1
    finally:
        _cleanup()


def test_ema_latency_smooths_average() -> None:
    from app.services.news_ingestion import _ema_latency

    assert _ema_latency(None, 120.0) == 120.0
    # alpha=0.3: 0.3*200 + 0.7*100 = 130
    assert _ema_latency(100.0, 200.0) == 130.0


def test_refresh_all_limits_to_given_sources(monkeypatch) -> None:
    class FakeResponse:
        text = "<rss><channel></channel></rss>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="Only Source",
        source_type="rss",
        url="https://feeds.example.com/only.xml",
        market="us",
    )

    with SessionLocal() as session:
        summary = NewsIngestionService(session).refresh_all(sources=[source])

    assert [result.source_name for result in summary.results] == ["Only Source"]
    # 空 RSS 通道按健康判定记 empty（非 http/parse 失败）
    assert summary.results[0].status == "empty"


def test_refresh_source_deduplicates_cross_source_similar_titles(monkeypatch) -> None:
    """不同主机、同窗口、近重复标题 → SimHash 跨源判重。"""

    class FakeResponse:
        text = json.dumps(
            {
                "data": [
                    {
                        "uuid": "story-1",
                        "title": "Nvidia tops quarterly revenue expectations again",
                        "description": "Wire one.",
                        "snippet": "Body one.",
                        "url": "https://wire-a.example.com/cross-1",
                        "published_at": "2026-03-26T05:00:00Z",
                    },
                    {
                        "uuid": "story-2",
                        "title": "NVIDIA tops quarterly revenue expectations, again",
                        "description": "Wire two.",
                        "snippet": "Body two.",
                        "url": "https://wire-b.example.com/cross-2",
                        "published_at": "2026-03-26T05:30:00Z",
                    },
                ]
            }
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())
    source = SourceDefinition(
        name="The News API",
        source_type="api",
        url="https://api.thenewsapi.com/v1/news/top",
        market="us",
        language="en",
        tier="secondary",
        parser="the_news_api_json",
    )
    url_hashes = [
        sha256(b"https://wire-a.example.com/cross-1").hexdigest(),
        sha256(b"https://wire-b.example.com/cross-2").hexdigest(),
    ]

    def _cleanup() -> None:
        with SessionLocal() as session:
            session.execute(
                delete(ArticleContent).where(
                    ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes)))
                )
            )
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()

    _cleanup()
    try:
        with SessionLocal() as session:
            result = NewsIngestionService(session)._refresh_source(source)
            stored_items = session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))).all()

            assert result.status == "ok"
            assert result.inserted_count == 1
            assert len(stored_items) == 1
    finally:
        _cleanup()


def test_default_sources_are_all_valid_and_unique() -> None:
    from app.services.ingestion.sources import _default_sources, _validate_source_definition

    sources = _default_sources()

    assert len(sources) == 26
    names = [source.name for source in sources]
    assert len(names) == len(set(names)), f"duplicate source names: {names}"
    for source in sources:
        _validate_source_definition(source)

    by_name = {source.name: source for source in sources}
    expected_flash_tier = {
        "CLS Telegraph": 100,
        "MarketWatch MarketPulse": 100,
        "Wallstreetcn Live": 100,
    }
    for name, expected_cadence in expected_flash_tier.items():
        assert by_name[name].cadence_seconds == expected_cadence, name

    wallstreetcn = by_name["Wallstreetcn Live"]
    assert wallstreetcn.parser == "wallstreetcn_live_json"
    assert wallstreetcn.source_type == "html"
