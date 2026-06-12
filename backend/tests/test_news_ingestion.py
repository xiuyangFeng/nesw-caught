import json
import os
from datetime import datetime, timezone
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.source_health import SourceHealth
from app.main import app
from app.repositories.source_health_repository import SourceHealthRepository
from app.schemas.news import NewsItemSummary
from app.services.news_ingestion import (
    RefreshSummary,
    NewsIngestionService,
    SourceDefinition,
    SourceItem,
    load_sources,
    _parse_minimax_detail_html,
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_zhipu_news_inline_json,
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
    assert items[0].published_at == datetime(2025, 3, 17, 10, 0, tzinfo=timezone.utc)


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
    assert item.published_at == datetime(2026, 3, 4, 0, 0, tzinfo=timezone.utc)
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    source_name = "Multi Market Feed"
    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)

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
                fetched_at=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
                ingest_status="ingested",
            )
        )
        session.commit()

    monkeypatch.setattr("app.db.initializer.engine", engine)
    monkeypatch.setattr("app.db.initializer.SessionLocal", testing_session)
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
                fetched_at=datetime(2026, 3, 17, 8, 0, tzinfo=timezone.utc),
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
                    published_at=datetime(2026, 3, 17, 7, 30, tzinfo=timezone.utc),
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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
        sha256("https://news.example.com/story-1".encode("utf-8")).hexdigest(),
        sha256("https://news.example.com/story-2?utm_source=wire".encode("utf-8")).hexdigest(),
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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
        sha256("https://news.example.com/cn-story-1".encode("utf-8")).hexdigest(),
        sha256("https://news.example.com/cn-story-2".encode("utf-8")).hexdigest(),
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
            now = datetime(2025, 3, 17, 10, 0, tzinfo=timezone.utc)
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
        published_at=datetime(2025, 3, 17, 9, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2025, 3, 17, 9, 1, tzinfo=timezone.utc),
        ingest_status="ingested",
    )

    class FakeNotificationService:
        def __init__(self) -> None:
            self.news_payloads: list[dict] = []

        def on_news_created(self, payload: dict) -> None:
            self.news_payloads.append(payload)

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

    class FakePipelineService:
        def __init__(self, session) -> None:
            self.session = session
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
          <title>Pipeline refresh item</title>
          <link>https://example.com/pipeline-refresh-item</link>
          <description>Fresh signal text</description>
          <pubDate>Wed, 19 Mar 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    url_hash = sha256("https://example.com/pipeline-refresh-item".encode("utf-8")).hexdigest()

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

    class FakeFactory:
        def create(self) -> FakeClient:
            return FakeClient()

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
    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", lambda: FakeFactory())
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
                    "title": "Pipeline refresh item",
                    "summary": "Fresh signal text",
                    "source_name": "Pipeline Refresh",
                    "canonical_url": "https://example.com/pipeline-refresh-item",
                    "market": "us",
                    "sentiment_label": None,
                    "editorial_score": None,
                    "published_at": "2026-03-19T10:00:00Z",
                    "fetched_at": inserted_payload["fetched_at"],
                },
            ),
            ("news.created_batch", {"news_ids": [inserted_id]}),
        ]
        assert calls == [[inserted_id]]

        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        session.commit()


def test_refresh_all_backfills_pending_news_when_no_new_items(monkeypatch) -> None:
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

    class FakeFactory:
        def create(self) -> FakeClient:
            return FakeClient()

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
    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", lambda: FakeFactory())
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
            published_at=datetime(2026, 3, 19, 11, 0, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 3, 19, 11, 1, tzinfo=timezone.utc),
            ingest_status="ingested",
        )
        session.add(pending)
        session.commit()

        summary = NewsIngestionService(session).refresh_all()

        assert summary.inserted_count == 0
        assert calls == [[pending.id]]

        session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.url_hash == url_hash))))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
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
        def __init__(self, session) -> None:
            self.session = session

        def process_news_ids(self, news_ids: list[int]):
            return type("Summary", (), {"news_ids": list(news_ids), "processed_count": len(news_ids)})()

    from app.workers.queue_worker import BackgroundQueueWorker, analysis_queue
    from datetime import datetime, timezone
    from typing import Any

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
            self.market = "us"
            self.published_at = datetime(2025, 3, 17, 9, 0, tzinfo=timezone.utc)
            self.fetched_at = datetime(2025, 3, 17, 9, 1, tzinfo=timezone.utc)

    class FakeNewsRepositoryForProcessed:
        def __init__(self, session) -> None:
            self.session = session
        def get_by_ids(self, news_ids: list[int]) -> list[Any]:
            return [FakeNewsItem(nid) for nid in news_ids]

    class FakeNotificationService:
        def on_news_created(self, payload: dict) -> None: pass

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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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
        sha256("https://news.example.com/boundary-1".encode("utf-8")).hexdigest(),
        sha256("https://news.example.com/boundary-2".encode("utf-8")).hexdigest(),
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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
    source = SourceDefinition(
        name="Only Source",
        source_type="rss",
        url="https://feeds.example.com/only.xml",
        market="us",
    )

    with SessionLocal() as session:
        summary = NewsIngestionService(session).refresh_all(sources=[source])

    assert [result.source_name for result in summary.results] == ["Only Source"]
    assert summary.results[0].status == "ok"


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

    class FakeHttpClientFactory:
        def create(self) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr("app.services.news_ingestion.HttpClientFactory", FakeHttpClientFactory)
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
        sha256("https://wire-a.example.com/cross-1".encode("utf-8")).hexdigest(),
        sha256("https://wire-b.example.com/cross-2".encode("utf-8")).hexdigest(),
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
