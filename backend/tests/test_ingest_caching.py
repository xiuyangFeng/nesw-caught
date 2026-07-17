import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.models.source_health import SourceHealth
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.ingestion.fetcher import fetch_source_items
from app.services.ingestion.fetcher import logger as fetcher_logger
from app.services.ingestion.persister import ItemPersister
from app.services.ingestion.persister import logger as persister_logger
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome, SourceItem


@pytest.fixture
def _reenable_ingestion_loggers():
    """Alembic env.py 用 `fileConfig(...)` 默认 disable_existing_loggers=True,
    会把 initialize_database() 执行前已 import 的 app.* logger 全部禁用
    (测试会话级 fixture 与生产启动都会触发)。这里仅为验证本文件新增的
    日志语句而在测试内局部临时启用,不改动 conftest.py / alembic env.py。
    """
    fetcher_previous = fetcher_logger.disabled
    persister_previous = persister_logger.disabled
    fetcher_logger.disabled = False
    persister_logger.disabled = False
    try:
        yield
    finally:
        fetcher_logger.disabled = fetcher_previous
        persister_logger.disabled = persister_previous


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
        # HTTP 200 with zero parsed items is an empty batch, not a hard success.
        assert result_200.status == "empty"

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


def test_fetcher_logs_source_context_on_failure(caplog, _reenable_ingestion_loggers) -> None:
    """异常治理:fetch_source_items 的兜底 except 之前吞错不留日志,现在必须带 source 上下文。"""
    bad_source = SourceDefinition(
        name="Unsupported Parser Source",
        source_type="html",
        url="https://example.com/bad-parser",
        market="us",
        parser="does_not_exist",
    )
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers({})
    mock_response.text = "<html></html>"

    with patch("app.services.news_ingestion.HttpClientFactory.create") as mock_factory:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_factory.return_value.__enter__.return_value = mock_client

        with caplog.at_level(logging.WARNING, logger="app.services.ingestion.fetcher"):
            outcome = fetch_source_items(bad_source)

    # 行为不变:仍然返回携带 error 字符串的 outcome,不抛出。
    assert outcome.error is not None
    assert "unsupported parser" in outcome.error

    # 新增质量要求:必须留下带 source 名称与 URL 的日志,不能是"吞错不留日志"。
    assert any(
        bad_source.name in record.getMessage() and bad_source.url in record.getMessage()
        for record in caplog.records
    )


def test_persister_logs_source_context_on_persist_outcome_failure(
    test_source, monkeypatch, caplog, _reenable_ingestion_loggers
) -> None:
    """异常治理:persist_outcome 的兜底 except 之前吞错不留日志,现在必须带 source 上下文。"""
    with SessionLocal() as session:
        session.query(SourceHealth).filter(SourceHealth.source_name == test_source.name).delete()
        session.commit()

        repo = SourceHealthRepository(session)
        persister = ItemPersister(session, repo)

        def _boom(source, item):
            raise RuntimeError("unexpected persist failure")

        monkeypatch.setattr(persister, "persist_item", _boom)

        outcome = SourceFetchOutcome(
            source=test_source,
            items=[
                SourceItem(
                    title="Boom",
                    canonical_url="https://example.com/rss-cached/boom",
                    summary=None,
                    content_text=None,
                    published_at=None,
                )
            ],
            error=None,
            latency_ms=5.0,
        )

        with caplog.at_level(logging.ERROR, logger="app.services.ingestion.persister"):
            result = persister.persist_outcome(outcome)

    # 行为不变:仍然返回 error 状态结果,不向上抛出(否则会中断同批其它 source 的落库)。
    assert result.status == "parse_error"
    assert result.error == "unexpected persist failure"

    assert any(
        test_source.name in record.getMessage() and test_source.url in record.getMessage()
        for record in caplog.records
    )


def test_persister_logs_context_when_minimax_detail_hydration_fails(caplog, _reenable_ingestion_loggers) -> None:
    """异常治理:hydrate_minimax_detail_item 原先失败时完全不留日志,现在必须带 URL 上下文。"""
    minimax_source = SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
    )
    canonical_url = "https://www.minimaxi.com/news/detail-hydration-fail-test"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    # 缺少 _parse_minimax_detail_html 期望的标记,触发其内部 ValueError。
    mock_response.text = "<html>no matching markers here</html>"
    mock_response.raise_for_status = lambda: None

    with SessionLocal() as session:
        session.query(SourceHealth).filter(SourceHealth.source_name == minimax_source.name).delete()
        session.commit()

        repo = SourceHealthRepository(session)
        persister = ItemPersister(session, repo)

        outcome = SourceFetchOutcome(
            source=minimax_source,
            items=[
                SourceItem(
                    title="NVIDIA raises revenue guidance on AI chip demand",
                    canonical_url=canonical_url,
                    summary="Earnings outlook lifted for data-center GPUs",
                    content_text=None,
                    published_at=None,
                )
            ],
            error=None,
            latency_ms=5.0,
        )

        try:
            with patch("app.services.news_ingestion.HttpClientFactory.create") as mock_factory:
                mock_client = MagicMock()
                mock_client.get.return_value = mock_response
                mock_factory.return_value.__enter__.return_value = mock_client

                with caplog.at_level(logging.WARNING, logger="app.services.ingestion.persister"):
                    result = persister.persist_outcome(outcome)

            # 行为不变:详情页补全失败时优雅降级为 extract_status="failed" 的原始 item,
            # 整个 source 仍记为成功,不因单条详情抓取失败而报错。
            assert result.status == "ok"
            assert result.inserted_count == 1

            assert any(canonical_url in record.getMessage() for record in caplog.records)
        finally:
            session.execute(NewsItem.__table__.delete().where(NewsItem.canonical_url == canonical_url))
            session.commit()
