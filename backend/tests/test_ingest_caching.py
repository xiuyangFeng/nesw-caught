import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import httpx

from app.db.session import SessionLocal
from app.models.source_health import SourceHealth
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.types import SourceDefinition
from app.services.ingestion.fetcher import fetch_source_items
from app.services.ingestion.persister import ItemPersister


@pytest.fixture
def test_source():
    return SourceDefinition(
        name="Test Cache Source",
        source_type="rss",
        url="https://example.com/rss-cached.xml",
        market="us",
        language="en",
    )


def test_fetcher_handles_304_and_200_with_headers(test_source):
    # 1. 模拟 304 Not Modified
    mock_response_304 = MagicMock(spec=httpx.Response)
    mock_response_304.status_code = 304
    mock_response_304.headers = httpx.Headers({})
    
    with patch("app.services.news_ingestion.HttpClientFactory.create") as mock_factory:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response_304
        mock_factory.return_value.__enter__.return_value = mock_client
        
        outcome_304 = fetch_source_items(test_source, etag="etag-123", last_modified="date-123")
        assert outcome_304.is_not_modified is True
        assert outcome_304.etag == "etag-123"
        assert outcome_304.last_modified == "date-123"
        assert len(outcome_304.items) == 0

    # 2. 模拟 200 OK 且返回最新 headers
    mock_response_200 = MagicMock(spec=httpx.Response)
    mock_response_200.status_code = 200
    mock_response_200.headers = httpx.Headers({"ETag": "new-etag", "Last-Modified": "new-date"})
    mock_response_200.text = "<rss version='2.0'><channel><title>Test</title></channel></rss>"
    
    with patch("app.services.news_ingestion.HttpClientFactory.create") as mock_factory:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response_200
        mock_factory.return_value.__enter__.return_value = mock_client
        
        outcome_200 = fetch_source_items(test_source)
        assert outcome_200.is_not_modified is False
        assert outcome_200.etag == "new-etag"
        assert outcome_200.last_modified == "new-date"


def test_persister_saves_headers_and_handles_304_outcome(test_source):
    with SessionLocal() as session:
        # 清理
        session.query(SourceHealth).filter(SourceHealth.source_name == test_source.name).delete()
        session.commit()

        repo = SourceHealthRepository(session)
        persister = ItemPersister(session, repo)

        # 1. 模拟 200 outcome 写入
        from app.services.ingestion.types import SourceFetchOutcome
        outcome_200 = SourceFetchOutcome(
            source=test_source,
            items=[],
            error=None,
            latency_ms=10.0,
            etag="etag-save-999",
            last_modified="date-save-999",
            is_not_modified=False
        )

        result_200 = persister.persist_outcome(outcome_200)
        assert result_200.status == "ok"
        
        # 验证数据库中已经存入 etag/date
        health = repo.get_or_create(
            source_name=test_source.name,
            source_type=test_source.source_type,
            market=test_source.market
        )
        assert health.last_etag == "etag-save-999"
        assert health.last_modified == "date-save-999"

        # 2. 模拟 304 outcome 写入
        outcome_304 = SourceFetchOutcome(
            source=test_source,
            items=[],
            error=None,
            latency_ms=5.0,
            etag="etag-save-999",
            last_modified="date-save-999",
            is_not_modified=True
        )
        result_304 = persister.persist_outcome(outcome_304)
        assert result_304.status == "not_modified"
        assert result_304.fetched_count == 0
        assert result_304.inserted_count == 0
