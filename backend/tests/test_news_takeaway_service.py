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


def test_generate_persists_empty_takeaway_and_prevents_retry() -> None:
    """LLM 明确返回空字符串(「无法判断」)时也应落库并计入 updated,
    避免 ai_takeaway 留 NULL 导致下次 feed layout 重建再次入队、反复调用 LLM 且绕开日配额。
    落库后 ai_takeaway 非 NULL,同一 id 再次调用 generate_for_ids 不应再命中 provider。"""
    provider = _FakeProvider({"takeaway": ""})
    with SessionLocal() as session:
        item = _make_item(session, suffix="empty")
        session.commit()
        item_id = item.id
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=provider),
            ):
                updated = service.generate_for_ids([item_id], batch_limit=10)
                session.commit()
                assert [i.id for i in updated] == [item_id]
                assert provider.calls == 1
                session.refresh(item)
                assert item.ai_takeaway == ""

                # 再次调用同一 id:ai_takeaway 已非 NULL(空字符串),.is_(None) 过滤应排除它,
                # provider 调用计数保持不变。
                updated_again = service.generate_for_ids([item_id], batch_limit=10)
                assert updated_again == []
                assert provider.calls == 1
        finally:
            _cleanup(session, [item_id])


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


def test_generate_continues_batch_after_single_item_failure() -> None:
    """batch_limit>=2 时,单条候选生成失败不应中断批次:
    第 1 条 provider 调用抛异常后,第 2 条仍被尝试并成功写库。"""

    class _FailFirstThenSucceedProvider:
        def __init__(self, payload: object) -> None:
            self._payload = payload
            self.calls = 0

        def analyze_json(self, *, prompt: str) -> object:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("llm down")
            return self._payload

    provider = _FailFirstThenSucceedProvider({"takeaway": "第二条结论"})
    with SessionLocal() as session:
        a = _make_item(session, suffix="fail-first")
        b = _make_item(session, suffix="fail-second")
        session.commit()
        ids = [a.id, b.id]
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=provider),
            ):
                updated = service.generate_for_ids(ids, batch_limit=2)
            session.commit()
            assert [item.id for item in updated] == [b.id]
            assert provider.calls == 2
            session.refresh(a)
            session.refresh(b)
            assert a.ai_takeaway is None
            assert b.ai_takeaway == "第二条结论"
        finally:
            _cleanup(session, ids)


def test_worker_daily_quota_exhausted_drops_candidates_and_clamps_batch_limit() -> None:
    """日配额=1 时:第一轮按 batch_limit=min(takeaway_batch_limit, quota) 钳制只生成 1 条;
    同一 worker 实例第二轮候选入队时配额已耗尽(quota<=0),整批被直接丢弃——
    不发布任何事件、DB 中新候选的 ai_takeaway 仍为 NULL。"""
    provider = _FakeProvider({"takeaway": "配额结论"})
    with SessionLocal() as session:
        a = _make_item(session, suffix="quota-a")
        b = _make_item(session, suffix="quota-b")
        c = _make_item(session, suffix="quota-c")
        session.commit()
        a_id, b_id, c_id = a.id, b.id, c.id
    ids = [a_id, b_id, c_id]
    published: list[tuple[str, dict]] = []
    try:
        enqueue_takeaway_candidates([a_id, b_id])
        worker = TakeawayWorker(session_factory=SessionLocal)
        settings = SimpleNamespace(
            ai_enabled=True, takeaway_batch_limit=12, takeaway_daily_limit=1, takeaway_poll_interval_seconds=5.0
        )
        fake_bus = SimpleNamespace(publish=lambda name, payload: published.append((name, payload)))
        with (
            patch.object(worker_module, "get_settings", return_value=settings),
            patch.object(worker_module, "get_event_bus", return_value=fake_bus),
            patch.object(takeaway_module, "build_provider", return_value=provider),
            patch.object(takeaway_module.LLMProviderConfigRepository, "get_active", return_value=object()),
        ):
            # 第一轮:两条候选入队,但 batch_limit 被钳制为 min(12, quota=1)=1,只生成 1 条
            processed_first = worker.do_cycle()
            assert processed_first == 1

            with SessionLocal() as check_session:
                a_takeaway = check_session.get(NewsItem, a_id).ai_takeaway
                b_takeaway = check_session.get(NewsItem, b_id).ai_takeaway
            generated = [tk for tk in (a_takeaway, b_takeaway) if tk is not None]
            skipped = [tk for tk in (a_takeaway, b_takeaway) if tk is None]
            assert len(generated) == 1
            assert len(skipped) == 1

            events_after_first_round = len(published)

            # 第二轮(同一 worker 实例):新候选入队,但当日配额已耗尽,整批被丢弃
            enqueue_takeaway_candidates([c_id])
            processed_second = worker.do_cycle()
            assert processed_second == 0
            assert len(published) == events_after_first_round

            with SessionLocal() as check_session:
                assert check_session.get(NewsItem, c_id).ai_takeaway is None
    finally:
        with SessionLocal() as session:
            _cleanup(session, ids)


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
