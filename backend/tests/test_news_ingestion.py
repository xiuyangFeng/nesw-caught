from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.news_ingestion import (
    RefreshSummary,
    SourceDefinition,
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
