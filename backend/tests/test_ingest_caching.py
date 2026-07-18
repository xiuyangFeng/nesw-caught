import logging
from datetime import UTC, datetime
from hashlib import sha256
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

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

    with patch("app.services.http_pool.get_feed_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response_304
        mock_get_client.return_value = mock_client

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

    with patch("app.services.http_pool.get_feed_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response_200
        mock_get_client.return_value = mock_client

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

    with patch("app.services.http_pool.get_feed_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

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


MINIMAX_DETAIL_HTML = r"""
<html>
  <head><title>MiniMax revenue surges on AI chip demand - MiniMax News | MiniMax</title></head>
  <body>
    <script>
      self.__next_f.push([1,"6:[[\"$\",\"$L17\",null,{\"data\":{\"base_resp\":{\"status_code\":0},\"title\":\"MiniMax revenue surges on AI chip demand\",\"content\":[{\"id\":\"article-title\",\"type\":\"ArticleTitle\",\"props\":{\"date\":\"2026-03-04\",\"title\":\"MiniMax revenue surges on AI chip demand\"},\"children\":[]},{\"id\":\"article-paragraph\",\"type\":\"ArticleParagraph\",\"props\":{\"content\":\"$18\"},\"children\":[]}],\"slug\":\"minimax-revenue-ai-chip-demand\"}}]]"]);
    </script>
    <script>
      self.__next_f.push([1,"\u003cdiv style=\"max-width: 768px;\"\u003e
      \u003cp\u003eMiniMax reported record revenue as AI chip demand lifted guidance.\u003c/p\u003e
      \u003c/div\u003e"]);
    </script>
  </body>
</html>
"""


def _minimax_source() -> SourceDefinition:
    return SourceDefinition(
        name="MiniMax News",
        source_type="html",
        url="https://www.minimaxi.com/news",
        market="hk",
        parser="anchor_list_html",
    )


class _FakeDetailResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


def _delete_news_by_url(session, canonical_url: str) -> None:
    from app.models.article_content import ArticleContent

    session.execute(
        ArticleContent.__table__.delete().where(
            ArticleContent.news_id.in_(select(NewsItem.id).where(NewsItem.canonical_url == canonical_url))
        )
    )
    session.execute(NewsItem.__table__.delete().where(NewsItem.canonical_url == canonical_url))
    session.commit()


def test_minimax_detail_hydration_fetches_and_parses(monkeypatch) -> None:
    """详情水合在并发阶段完成:抓详情页并解析出 published_at / 正文。"""
    from app.services.ingestion.detail_hydration import (
        DetailFetchCooldown,
        hydrate_minimax_detail_items,
    )

    canonical_url = "https://www.minimaxi.com/news/hydration-ok-test"
    calls: list[str] = []

    class FakeClient:
        def get(self, url: str):
            calls.append(url)
            return _FakeDetailResponse(MINIMAX_DETAIL_HTML)

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    item = SourceItem(
        title="MiniMax revenue surges on AI chip demand",
        canonical_url=canonical_url,
        summary=None,
        content_text=None,
        published_at=None,
    )

    with SessionLocal() as session:
        _delete_news_by_url(session, canonical_url)
        hydrated = hydrate_minimax_detail_items(
            session, _minimax_source(), [item], cooldown=DetailFetchCooldown()
        )

    assert calls == [canonical_url]
    assert hydrated[0].published_at == datetime(2026, 3, 4, tzinfo=UTC)
    assert "record revenue" in (hydrated[0].content_text or "")
    # parser 不设置 extract_status;落库段按 content_text 推导为 "success"。
    assert hydrated[0].extract_status is None


def test_minimax_detail_hydration_skips_complete_existing(monkeypatch) -> None:
    """已存在且 published_at + 正文完整的记录不再重抓详情页。"""
    from app.models.article_content import ArticleContent
    from app.services.ingestion.detail_hydration import (
        DetailFetchCooldown,
        hydrate_minimax_detail_items,
    )

    canonical_url = "https://www.minimaxi.com/news/hydration-skip-test"
    url_hash = sha256(canonical_url.encode("utf-8")).hexdigest()

    class FakeClient:
        def get(self, url: str):
            raise AssertionError("complete existing item must not trigger detail fetch")

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    item = SourceItem(
        title="MiniMax revenue surges on AI chip demand",
        canonical_url=canonical_url,
        summary=None,
        content_text=None,
        published_at=None,
    )

    with SessionLocal() as session:
        _delete_news_by_url(session, canonical_url)
        news = NewsItem(
            source_name="MiniMax News",
            source_url="https://www.minimaxi.com/news",
            title="MiniMax revenue surges on AI chip demand",
            summary="done",
            canonical_url=canonical_url,
            url_hash=url_hash,
            market="hk",
            language="zh",
            published_at=datetime(2026, 3, 4, tzinfo=UTC),
            fetched_at=datetime(2026, 3, 4, tzinfo=UTC),
            effective_at=datetime(2026, 3, 4, tzinfo=UTC),
            ingest_status="ingested",
        )
        session.add(news)
        session.flush()
        session.add(
            ArticleContent(
                news_id=news.id,
                content_text="完整正文",
                content_html="<p>完整正文</p>",
                extract_status="success",
                extracted_at=datetime(2026, 3, 4, tzinfo=UTC),
            )
        )
        session.commit()

        try:
            hydrated = hydrate_minimax_detail_items(
                session, _minimax_source(), [item], cooldown=DetailFetchCooldown()
            )
            assert hydrated == [item]
        finally:
            _delete_news_by_url(session, canonical_url)


def test_minimax_detail_hydration_cooldown_blocks_after_max_attempts(monkeypatch) -> None:
    """持续失败的 detail URL 在窗口内最多重试 N 次,超出后进入冷却不再请求。"""
    from app.services.ingestion.detail_hydration import (
        DetailFetchCooldown,
        hydrate_minimax_detail_items,
    )

    canonical_url = "https://www.minimaxi.com/news/hydration-cooldown-test"
    calls: list[str] = []

    class FakeClient:
        def get(self, url: str):
            calls.append(url)
            raise RuntimeError("detail page boom")

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    def _item() -> SourceItem:
        return SourceItem(
            title="MiniMax revenue surges on AI chip demand",
            canonical_url=canonical_url,
            summary=None,
            content_text=None,
            published_at=None,
        )

    cooldown = DetailFetchCooldown(max_attempts=3, window_seconds=86400.0)
    with SessionLocal() as session:
        _delete_news_by_url(session, canonical_url)
        for _ in range(3):
            hydrated = hydrate_minimax_detail_items(session, _minimax_source(), [_item()], cooldown=cooldown)
            assert hydrated[0].extract_status == "failed"
        assert len(calls) == 3

        # 第 4 次:冷却生效,不再发请求,原 item 透传(不再标记 failed)
        hydrated = hydrate_minimax_detail_items(session, _minimax_source(), [_item()], cooldown=cooldown)
        assert len(calls) == 3
        assert hydrated[0].extract_status is None

        # clear 后允许重试
        cooldown.clear()
        hydrate_minimax_detail_items(session, _minimax_source(), [_item()], cooldown=cooldown)
        assert len(calls) == 4


def test_minimax_detail_hydration_logs_url_on_failure(monkeypatch, caplog, _reenable_ingestion_loggers) -> None:
    """异常治理:详情页补全失败必须留下带 URL 上下文的日志,并优雅降级。"""
    import logging as _logging

    from app.services.ingestion.detail_hydration import (
        DetailFetchCooldown,
        hydrate_minimax_detail_items,
    )
    from app.services.ingestion.detail_hydration import (
        logger as hydration_logger,
    )

    hydration_logger.disabled = False
    canonical_url = "https://www.minimaxi.com/news/detail-hydration-fail-test"

    class FakeClient:
        def get(self, url: str):
            return _FakeDetailResponse("<html>no matching markers here</html>")

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: FakeClient())

    item = SourceItem(
        title="NVIDIA raises revenue guidance on AI chip demand",
        canonical_url=canonical_url,
        summary="Earnings outlook lifted for data-center GPUs",
        content_text=None,
        published_at=None,
    )

    with SessionLocal() as session:
        _delete_news_by_url(session, canonical_url)
        with caplog.at_level(_logging.WARNING, logger="app.services.ingestion.detail_hydration"):
            hydrated = hydrate_minimax_detail_items(
                session, _minimax_source(), [item], cooldown=DetailFetchCooldown()
            )

    # 优雅降级:单条详情失败返回 extract_status="failed" 的回退 item。
    assert hydrated[0].extract_status == "failed"
    assert any(canonical_url in record.getMessage() for record in caplog.records)


def test_persist_outcome_does_not_fetch_minimax_details(monkeypatch) -> None:
    """详情水合已挪出串行落库段:persist_outcome 不允许再发任何 HTTP 请求。"""
    monkeypatch.setattr(
        "app.services.http_pool.get_feed_client",
        lambda: pytest.fail("persist path must not perform HTTP"),
    )

    canonical_url = "https://www.minimaxi.com/news/persist-no-http-test"
    with SessionLocal() as session:
        _delete_news_by_url(session, canonical_url)
        session.query(SourceHealth).filter(SourceHealth.source_name == "MiniMax News").delete()
        session.commit()

        repo = SourceHealthRepository(session)
        persister = ItemPersister(session, repo)

        outcome = SourceFetchOutcome(
            source=_minimax_source(),
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
            result = persister.persist_outcome(outcome)
            assert result.status == "ok"
            assert result.inserted_count == 1
        finally:
            _delete_news_by_url(session, canonical_url)
