from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.services import news_takeaway as takeaway_module
from app.services.news_takeaway import NewsTakeawayService, enqueue_takeaway_candidates, takeaway_queue
from app.workers import takeaway_worker as worker_module
from app.workers.takeaway_worker import TakeawayWorker


class _FakeProvider:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.calls = 0

    def analyze_json(self, *, prompt: str) -> object:
        self.calls += 1
        return self._payload


def _make_item(session, *, suffix: str, takeaway: str | None = None) -> NewsItem:
    item = NewsItem(
        source_name="UnitTest",
        source_url=f"https://example.com/tk-{suffix}",
        title=f"takeaway {suffix}",
        canonical_url=f"https://example.com/tk-{suffix}",
        url_hash=f"hash-tk-{suffix}",
        market="us",
        fetched_at=datetime.now(timezone.utc),
        ai_takeaway=takeaway,
    )
    session.add(item)
    session.flush()
    return item


def _cleanup(session, ids: list[int]) -> None:
    for news_id in ids:
        row = session.get(NewsItem, news_id)
        if row is not None:
            session.delete(row)
    session.commit()


def test_generate_skips_items_with_existing_takeaway() -> None:
    provider = _FakeProvider({"takeaway": "一句话结论"})
    with SessionLocal() as session:
        fresh = _make_item(session, suffix="fresh")
        done = _make_item(session, suffix="done", takeaway="已有结论")
        session.commit()
        ids = [fresh.id, done.id]
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=provider),
            ):
                updated = service.generate_for_ids(ids, batch_limit=10)
            session.commit()
            assert [item.id for item in updated] == [fresh.id]
            assert provider.calls == 1
            session.refresh(fresh)
            assert fresh.ai_takeaway == "一句话结论"
        finally:
            _cleanup(session, ids)


def test_generate_respects_batch_limit_and_tolerates_failure() -> None:
    class _FailingProvider:
        def analyze_json(self, *, prompt: str) -> object:
            raise RuntimeError("llm down")

    with SessionLocal() as session:
        a = _make_item(session, suffix="a")
        b = _make_item(session, suffix="b")
        session.commit()
        ids = [a.id, b.id]
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=_FailingProvider()),
            ):
                updated = service.generate_for_ids(ids, batch_limit=1)
            assert updated == []
        finally:
            _cleanup(session, ids)


def test_generate_without_active_config_is_noop() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="noconf")
        session.commit()
        try:
            service = NewsTakeawayService(session)
            with patch.object(service.config_repository, "get_active", return_value=None):
                assert service.generate_for_ids([item.id], batch_limit=5) == []
        finally:
            _cleanup(session, [item.id])


def test_worker_drains_queue_when_ai_disabled() -> None:
    enqueue_takeaway_candidates([1, 2, 3])
    worker = TakeawayWorker(session_factory=SessionLocal)
    settings = SimpleNamespace(
        ai_enabled=False, takeaway_batch_limit=12, takeaway_daily_limit=300, takeaway_poll_interval_seconds=5.0
    )
    with patch.object(worker_module, "get_settings", return_value=settings):
        assert worker.do_cycle() == 0
    assert takeaway_queue.empty()


def test_worker_generates_and_publishes() -> None:
    provider = _FakeProvider({"takeaway": "批量结论"})
    with SessionLocal() as session:
        item = _make_item(session, suffix="worker")
        session.commit()
        item_id = item.id
    published: list[tuple[str, dict]] = []
    try:
        enqueue_takeaway_candidates([item_id])
        worker = TakeawayWorker(session_factory=SessionLocal)
        settings = SimpleNamespace(
            ai_enabled=True, takeaway_batch_limit=12, takeaway_daily_limit=300, takeaway_poll_interval_seconds=5.0
        )
        fake_bus = SimpleNamespace(publish=lambda name, payload: published.append((name, payload)))
        with (
            patch.object(worker_module, "get_settings", return_value=settings),
            patch.object(worker_module, "get_event_bus", return_value=fake_bus),
            patch.object(takeaway_module, "build_provider", return_value=provider),
            patch.object(takeaway_module.LLMProviderConfigRepository, "get_active", return_value=object()),
        ):
            processed = worker.do_cycle()
        assert processed == 1
        event_names = [name for name, _ in published]
        assert "news.updated" in event_names
        assert "news.signals_processed" in event_names
        updated_payload = next(payload for name, payload in published if name == "news.updated")
        assert updated_payload["updated_fields"] == ["ai_takeaway"]
        with SessionLocal() as session:
            assert session.get(NewsItem, item_id).ai_takeaway == "批量结论"
    finally:
        with SessionLocal() as session:
            _cleanup(session, [item_id])
