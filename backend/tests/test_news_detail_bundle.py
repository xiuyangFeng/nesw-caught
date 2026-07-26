from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_repository import NewsRepository


def _make_item(session, *, suffix: str) -> NewsItem:
    item = NewsItem(
        source_name="UnitTest",
        source_url=f"https://example.com/{suffix}",
        title=f"bundle {suffix}",
        canonical_url=f"https://example.com/bundle-{suffix}",
        url_hash=f"hash-bundle-{suffix}",
        market="us",
        fetched_at=datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def test_get_detail_bundle_returns_all_parts() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="full")
        session.add(ArticleContent(news_id=item.id, content_text="正文", extract_status="success"))
        session.add(
            NewsStockMention(news_id=item.id, symbol="NVDA", market="us", mention_type="explicit", confidence=0.9)
        )
        topic = TopicCluster(
            topic_key="bundle-topic", topic_title="Bundle Topic", last_seen_at=datetime.now(UTC)
        )
        session.add(topic)
        session.flush()
        session.add(TopicNewsLink(topic_cluster_id=topic.id, news_id=item.id))
        session.commit()
        try:
            bundle = NewsRepository(session).get_detail_bundle(item.id)
            assert bundle is not None
            assert bundle.item.id == item.id
            assert bundle.article is not None and bundle.article.content_text == "正文"
            assert [m.symbol for m in bundle.mentions] == ["NVDA"]
            assert bundle.topic is not None and bundle.topic.topic_title == "Bundle Topic"
        finally:
            session.rollback()
            for table in ("topic_news_link", "news_stock_mention", "article_content"):
                session.execute(sa.text(f"DELETE FROM {table} WHERE news_id = :v"), {"v": item.id})
            session.execute(sa.text("DELETE FROM topic_cluster WHERE topic_key = 'bundle-topic'"))
            session.delete(session.get(NewsItem, item.id))
            session.commit()


def test_get_detail_bundle_handles_missing_parts() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="bare")
        session.commit()
        try:
            bundle = NewsRepository(session).get_detail_bundle(item.id)
            assert bundle is not None
            assert bundle.article is None
            assert bundle.mentions == []
            assert bundle.topic is None
        finally:
            session.delete(session.get(NewsItem, item.id))
            session.commit()


def test_get_detail_bundle_missing_news_returns_none() -> None:
    with SessionLocal() as session:
        assert NewsRepository(session).get_detail_bundle(987654321) is None


def test_detail_api_shape_unchanged() -> None:
    client = TestClient(app)
    with SessionLocal() as session:
        item = _make_item(session, suffix="api")
        session.commit()
        item_id = item.id
    try:
        response = client.get(f"/api/news/{item_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == item_id
        assert payload["mentions"] == []
        assert payload["article"] is None
        assert payload["topic"] is None
    finally:
        with SessionLocal() as session:
            session.delete(session.get(NewsItem, item_id))
            session.commit()
