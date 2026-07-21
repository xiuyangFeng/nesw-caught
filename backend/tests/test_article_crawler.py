from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.services.ingestion.article_crawler import (
    DEFAULT_CRAWL_TIMEOUT_SECONDS,
    crawl_and_extract_article,
)
from app.services.news_signal_pipeline import NewsSignalPipelineService


def test_default_crawl_timeout_is_module_level_constant():
    # 15s 超时应是模块级常量而非散落在函数签名里的魔法数字，方便统一调整
    assert DEFAULT_CRAWL_TIMEOUT_SECONDS == 15.0

    import inspect

    signature = inspect.signature(crawl_and_extract_article)
    assert signature.parameters["timeout"].default == DEFAULT_CRAWL_TIMEOUT_SECONDS


def test_article_crawler_extracts_core_text():
    html_content = """
    <html>
        <head><title>Test Title</title></head>
        <body>
            <header>
                <nav>Header Navigation</nav>
            </header>
            <article>
                <h1>Amazing AI News</h1>
                <p>Paragraph 1: Artificial intelligence is transforming the financial sector in deep ways.</p>
                <p>Paragraph 2: Many platform companies are seeing expanding monetization paths.</p>
            </article>
            <footer>
                <p>Footer copyright info 2026</p>
            </footer>
        </body>
    </html>
    """

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = html_content

    with patch("httpx.Client.get", return_value=mock_response):
        content = crawl_and_extract_article("https://example.com/ai-post")
        # 应该只提取正文段落，忽略导航和页脚
        assert "Paragraph 1" in content
        assert "Paragraph 2" in content
        assert "Header Navigation" not in content
        assert "Footer copyright" not in content


def test_pipeline_automatically_crawls_missing_body():
    # 模拟网页返回
    html_content = """
    <html>
        <body>
            <article>
                <p>Detailed analysis of Apple's stock price movement and supply chain checks.</p>
            </article>
        </body>
    </html>
    """
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = html_content

    with SessionLocal() as session:
        # 1. 准备种子新闻，没有正文记录
        news_item = NewsItem(
            source_name="Bloomberg",
            source_url="https://example.com/bloomberg",
            title="Apple Supply Checks",
            summary="Softness in orders",
            canonical_url="https://example.com/apple-supply-test",
            url_hash="test-pipeline-crawl-hash",
            market="us",
            language="en",
            sentiment_label=None,
            sentiment_score=None,
            published_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            ingest_status="ingested",
        )
        # 清理原先记录
        session.query(ArticleContent).filter(ArticleContent.news_id == news_item.id).delete()
        session.query(NewsItem).filter(NewsItem.url_hash == news_item.url_hash).delete()
        session.add(news_item)
        session.commit()

        # 2. 模拟爬虫调用并运行管线
        with patch("httpx.Client.get", return_value=mock_response), \
             patch("app.services.news_signal_classifier.NewsSignalClassifier.classify") as mock_classify:

            # 模拟 AI 分类器正常处理并返回
            mock_classify.return_value = MagicMock(
                topic_key="apple_supply",
                topic_title_hint="Apple Supply Chain",
                topic_summary_hint="Summary",
                keywords=["Apple"],
                sentiment_label="negative",
                sentiment_score=-0.6,
                signal_confidence=0.9,
                classifier_type="rule",
                llm_error=None,
                summary="Apple supply drop"
            )

            pipeline = NewsSignalPipelineService(session)
            summary = pipeline.process_news_ids([news_item.id])

            assert summary.processed_count == 1

            # 3. 验证数据库中已经自动填充了正文
            article = session.query(ArticleContent).filter(ArticleContent.news_id == news_item.id).first()
            assert article is not None
            assert article.extract_status == "success"
            assert "Detailed analysis" in article.content_text

            # 验证 AI 分类器接收到了爬取出来的正文
            mock_classify.assert_called_once()
            _, kwargs = mock_classify.call_args
            assert "Detailed analysis" in kwargs["body"]

            # 清理
            session.delete(article)
            session.delete(news_item)
            session.commit()
