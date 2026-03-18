from datetime import datetime, timezone
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.main import app
from app.services.news_ingestion import (
    RefreshSummary,
    NewsIngestionService,
    SourceDefinition,
    SourceItem,
    _parse_minimax_detail_html,
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_zhipu_news_inline_json,
)


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

    class FakeIngestionService:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self) -> RefreshSummary:
            now = datetime(2025, 3, 17, 10, 0, tzinfo=timezone.utc)
            from app.services.news_ingestion import SourceFetchResult

            return RefreshSummary(
                started_at=now,
                finished_at=now,
                fetched_count=5,
                inserted_count=1,
                inserted_items=[inserted_item],
                results=[
                    SourceFetchResult(
                        source_name="Inserted Source",
                        source_type="rss",
                        status="ok",
                        fetched_count=5,
                        inserted_count=1,
                        error=None,
                        latency_ms=12.3,
                    )
                ],
            )

    class FakeNotificationService:
        def __init__(self) -> None:
            self.news_payloads: list[dict] = []

        def on_news_created(self, payload: dict) -> None:
            self.news_payloads.append(payload)

    class FakeNewsRepository:
        def __init__(self, session) -> None:
            self.session = session

        def list_recent(self, limit: int):  # pragma: no cover - route-level guard
            return [
                NewsItem(
                    id=1000,
                    source_name="Wrong Source",
                    source_url="https://example.com/feed",
                    title="Wrong recent news",
                    summary="Wrong summary",
                    canonical_url="https://example.com/wrong",
                    url_hash="wrong-hash",
                    market="hk",
                    language="zh",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=datetime(2025, 3, 17, 9, 30, tzinfo=timezone.utc),
                    fetched_at=datetime(2025, 3, 17, 9, 31, tzinfo=timezone.utc),
                    ingest_status="ingested",
                )
            ]

    notification_service = FakeNotificationService()
    monkeypatch.setattr("app.api.routes.news.NewsIngestionService", FakeIngestionService)
    monkeypatch.setattr("app.api.routes.news.NewsRepository", FakeNewsRepository)
    monkeypatch.setattr("app.api.routes.news.get_notification_service", lambda: notification_service)

    client = TestClient(app)
    response = client.post("/api/news/refresh")

    assert response.status_code == 200
    assert notification_service.news_payloads == [
        {
            "title": "Inserted news",
            "summary": "Inserted summary",
            "source_name": "Inserted Source",
            "market": "us",
            "published_at": "2025-03-17T09:00:00+00:00",
        }
    ]
