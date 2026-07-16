from datetime import datetime, timezone

import sqlalchemy as sa

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.schemas.news import NewsItemSummary


def test_news_item_table_has_ai_takeaway_column() -> None:
    with SessionLocal() as session:
        inspector = sa.inspect(session.get_bind())
        columns = {column["name"] for column in inspector.get_columns("news_item")}
    assert "ai_takeaway" in columns


def test_news_item_summary_carries_ai_takeaway() -> None:
    with SessionLocal() as session:
        item = NewsItem(
            source_name="UnitTest",
            source_url="https://example.com/takeaway",
            title="takeaway contract",
            canonical_url="https://example.com/takeaway-contract",
            url_hash="hash-takeaway-contract",
            market="us",
            fetched_at=datetime.now(timezone.utc),
            ai_takeaway="测试结论:偏利好",
        )
        session.add(item)
        session.commit()
        try:
            view = NewsItemSummary.model_validate(item, from_attributes=True)
            assert view.ai_takeaway == "测试结论:偏利好"
        finally:
            session.delete(item)
            session.commit()
