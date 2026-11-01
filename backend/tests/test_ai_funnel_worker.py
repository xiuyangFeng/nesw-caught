"""AI 漏斗 worker：无默认模型/关闭/超预算时空转；L1 → L2 → 提醒；失败用尽回退关键词；AI 在线判定。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.llm_provider_config import LLMProviderConfig
from app.models.llm_token_usage import LLMTokenUsage
from app.models.news_ai import NewsAiAnalysis, NewsAiScreen, NewsImpact
from app.models.news_item import NewsItem
from app.models.sector import StockSector
from app.models.watchlist_item import WatchlistItem
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.services.ai.llm_json import FunnelModel
from app.services.ai.status import AiModeChecker, funnel_status, inactive_reason
from app.workers.ai_funnel_worker import AiFunnelWorker

NOW = datetime(2031, 6, 3, 2, 0, tzinfo=UTC)


class FakeProvider:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.operations: list[str] = []

    def complete(self, *, messages, response_format=None, operation_type="chat"):
        self.operations.append(operation_type)
        response = self.handler(operation_type, messages)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(content=json.dumps(response, ensure_ascii=False))


class RecordingAlerts:
    def __init__(self) -> None:
        self.impacts: list[dict] = []
        self.fallback: list[dict] = []

    def on_news_impacts(self, news, *, overseas, major, view, impacts):
        self.impacts.append({"news": news, "overseas": overseas, "major": major, "view": view,
                             "impacts": list(impacts)})
        return 0

    def on_news_keyword_fallback(self, items):
        self.fallback.extend(items)
        return 0


@pytest.fixture(autouse=True)
def _clean():
    def wipe() -> None:
        with SessionLocal() as session:
            ids = list(session.scalars(select(NewsItem.id).where(NewsItem.source_name == "ai-worker-test")))
            for model in (NewsImpact, NewsAiAnalysis, NewsAiScreen):
                session.execute(delete(model).where(model.news_id.in_(ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(ids)))
            session.execute(delete(StockSector))
            session.execute(delete(WatchlistItem))
            session.execute(delete(LLMProviderConfig))
            session.execute(delete(LLMTokenUsage))
            session.execute(delete(WorkerRuntimeStatus).where(WorkerRuntimeStatus.worker_name == "ai_funnel"))
            session.commit()

    wipe()
    yield
    wipe()


def _seed_news(title: str, *, minutes_ago: int = 5) -> int:
    with SessionLocal() as session:
        published = NOW - timedelta(minutes=minutes_ago)
        item = NewsItem(source_name="ai-worker-test", source_url="https://example.com", title=title,
                        canonical_url=f"https://example.com/{title}", url_hash=f"ai-worker-{title}", market="us",
                        published_at=published, fetched_at=published)
        session.add(item)
        if session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == "688256.SH")) is None:
            session.add(WatchlistItem(symbol="688256.SH", market="cn", display_name="寒武纪", position_size=100))
            session.add(StockSector(symbol="688256.SH", sector="半导体", source="ai"))
        session.commit()
        return item.id


def _default_model(*, budget: float | None = None, is_default: bool = True) -> None:
    with SessionLocal() as session:
        session.add(LLMProviderConfig(provider_name="openai_compatible", model_name="gpt-6.1-terra", api_key="x",
                                      is_active=True, is_default=is_default, input_price_per_1m=0.15,
                                      output_price_per_1m=0.75, monthly_budget_usd=budget))
        session.commit()


def _worker(provider, alerts, **kwargs) -> AiFunnelWorker:
    return AiFunnelWorker(
        session_factory=SessionLocal,
        alert_service=alerts,
        model_resolver=lambda session: FunnelModel(config_id=1, model_name="gpt-6.1-terra", provider=provider),
        clock=lambda: NOW,
        **kwargs,
    )


def _handler(news_id: int, *, screen_error: bool = False):
    def handle(operation, messages):
        if operation == "ai_screen":
            if screen_error:
                return {"items": []}
            return {"items": [{"id": news_id, "importance": 3, "overseas": True, "deep_read": True,
                               "title_zh": "英伟达业绩超预期", "reason": "r"}]}
        if operation == "ai_impact":
            return {"summary_zh": "s", "view": "利好寒武纪", "major": True, "impacts": [
                {"target_type": "stock", "code": "688256", "name": "寒武纪", "direction": "bullish",
                 "strength": "strong", "rationale": "需求"}]}
        raise AssertionError(operation)
    return handle


def test_cycle_runs_screen_then_impact_then_alerts() -> None:
    news_id = _seed_news("Nvidia beats")
    provider = FakeProvider(_handler(news_id))
    alerts = RecordingAlerts()
    assert _worker(provider, alerts).do_cycle() == 2
    assert provider.operations == ["ai_screen", "ai_impact"]  # 已有板块，不再推断
    [call] = alerts.impacts
    assert call["news"]["id"] == news_id and call["news"]["title_zh"] == "英伟达业绩超预期"
    assert call["overseas"] and call["major"] and call["view"] == "利好寒武纪"
    assert call["impacts"][0]["code"] == "688256.SH"
    assert alerts.fallback == []


def test_stale_news_is_analyzed_but_not_alerted() -> None:
    news_id = _seed_news("old", minutes_ago=7 * 60)
    alerts = RecordingAlerts()
    _worker(FakeProvider(_handler(news_id)), alerts).do_cycle()
    assert alerts.impacts == []
    with SessionLocal() as session:
        assert session.scalar(select(NewsAiAnalysis).where(NewsAiAnalysis.news_id == news_id)) is not None


def test_exhausted_screen_is_left_to_the_alert_sweeper() -> None:
    """重试用尽的新闻由 AlertService.sweep_deferred 统一兜底，worker 自己不补发。"""
    news_id = _seed_news("寒武纪发布新品")
    alerts = RecordingAlerts()
    worker = _worker(FakeProvider(_handler(news_id, screen_error=True)), alerts, max_attempts=2)
    worker.do_cycle()
    worker.do_cycle()
    assert alerts.fallback == [] and alerts.impacts == []
    with SessionLocal() as session:
        row = session.scalar(select(NewsAiScreen).where(NewsAiScreen.news_id == news_id))
        assert row.status == "error" and row.attempts == 2


def test_worker_idles_without_explicit_default_model() -> None:
    _seed_news("x")
    _default_model(is_default=False)
    provider = FakeProvider(lambda op, messages: AssertionError("should not call"))
    worker = AiFunnelWorker(session_factory=SessionLocal, alert_service=RecordingAlerts(), clock=lambda: NOW)
    assert worker.do_cycle() == 0
    assert provider.operations == []


def test_worker_pauses_when_budget_set_without_prices() -> None:
    _seed_news("x")
    _default_model(budget=5.0)
    with SessionLocal() as session:
        config = session.scalar(select(LLMProviderConfig))
        config.input_price_per_1m = None
        config.output_price_per_1m = None
        session.commit()
    provider = FakeProvider(lambda op, messages: AssertionError("should not call"))
    assert _worker(provider, RecordingAlerts()).do_cycle() == 0
    assert provider.operations == []


def test_worker_pauses_when_over_budget() -> None:
    _seed_news("x")
    _default_model(budget=0.0001)
    with SessionLocal() as session:
        session.add(LLMTokenUsage(model_name="gpt-6.1-terra", prompt_tokens=1_000_000, completion_tokens=0,
                                  total_tokens=1_000_000, operation_type="ai_screen", created_at=NOW))
        session.commit()
    provider = FakeProvider(lambda op, messages: AssertionError("should not call"))
    assert _worker(provider, RecordingAlerts()).do_cycle() == 0
    assert provider.operations == []


def test_inactive_reason_and_mode_checker() -> None:
    with SessionLocal() as session:
        assert inactive_reason(session, NOW) == "no_default_model"
    _default_model()
    with SessionLocal() as session:
        assert inactive_reason(session, NOW) == "worker_not_running"
        session.add(WorkerRuntimeStatus(worker_name="ai_funnel", status="ok", last_heartbeat_at=NOW,
                                        last_success_at=NOW, cycle_count=1, success_count=1, failure_count=0,
                                        last_quotes_count=0))
        session.commit()
        assert inactive_reason(session, NOW) is None
        assert inactive_reason(session, NOW + timedelta(minutes=11)) == "worker_not_running"

        # 周期持续报错时心跳仍在刷新，但没有成功周期 → 不算在线（否则持仓新闻会两头落空）
        row = session.scalar(select(WorkerRuntimeStatus).where(WorkerRuntimeStatus.worker_name == "ai_funnel"))
        row.last_heartbeat_at = NOW + timedelta(minutes=30)
        session.commit()
        assert inactive_reason(session, NOW + timedelta(minutes=30)) == "worker_not_running"

    checker = AiModeChecker(session_factory=SessionLocal, ttl_seconds=0)
    # 心跳是 2031 年的"未来"时间，相对真实当前时间仍算新鲜
    assert checker() is True


def test_inactive_when_daily_quota_used_up_or_budget_unpriced(monkeypatch) -> None:
    _default_model()
    with SessionLocal() as session:
        session.add(WorkerRuntimeStatus(worker_name="ai_funnel", status="ok", last_heartbeat_at=NOW,
                                        last_success_at=NOW, cycle_count=1, success_count=1, failure_count=0,
                                        last_quotes_count=0))
        session.commit()
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "ai_impact_daily_limit", 0)
        assert inactive_reason(session, NOW) == "quota_exhausted"
        monkeypatch.setattr(get_settings(), "ai_impact_daily_limit", 300)

        config = session.scalar(select(LLMProviderConfig))
        config.input_price_per_1m = None
        config.output_price_per_1m = None
        config.monthly_budget_usd = 5.0
        session.commit()
        # 设了预算却没填单价 → 预算闸形同虚设，宁可停用
        assert inactive_reason(session, NOW) == "budget_unpriced"


def test_funnel_status_reports_today_counts_and_cost() -> None:
    news_id = _seed_news("Nvidia beats")
    _default_model()
    with SessionLocal() as session:
        session.add(NewsAiScreen(news_id=news_id, importance=3, overseas=True, deep_read=True, status="ok",
                                 attempts=1, screened_at=NOW))
        session.add(LLMTokenUsage(model_name="gpt-6.1-terra", prompt_tokens=2_000_000, completion_tokens=400_000,
                                  total_tokens=2_400_000, operation_type="ai_screen", created_at=NOW))
        session.commit()
        status = funnel_status(session, NOW)
    assert status["model_name"] == "gpt-6.1-terra"
    assert status["today"]["screened"] == 1
    screen_usage = next(entry for entry in status["usage"] if entry["operation_type"] == "ai_screen")
    assert screen_usage["calls"] == 1
    assert screen_usage["cost_usd"] == pytest.approx(2 * 0.15 + 0.4 * 0.75)
    assert status["today"]["cost_usd"] == pytest.approx(0.6)


def test_sector_inference_gives_up_after_repeated_failures() -> None:
    _seed_news("x", minutes_ago=60 * 30)  # 新闻在 24 小时窗口外，本测试只看板块推断
    with SessionLocal() as session:
        session.execute(delete(StockSector))
        session.commit()

    def handle(operation, messages):
        assert operation == "sector_infer"
        return {"sectors": []}

    provider = FakeProvider(handle)
    worker = _worker(provider, RecordingAlerts())
    for _ in range(5):
        worker.do_cycle()
    assert provider.operations.count("sector_infer") == 3


def test_alert_failure_for_one_news_does_not_block_others() -> None:
    first = _seed_news("first")
    second = _seed_news("second", minutes_ago=6)

    def handle(operation, messages):
        if operation == "ai_screen":
            return {"items": [{"id": news_id, "importance": 3, "overseas": False, "deep_read": True}
                              for news_id in (first, second)]}
        return {"summary_zh": "s", "view": "v", "major": False, "impacts": [
            {"target_type": "stock", "code": "688256", "name": "寒武纪", "direction": "bullish",
             "strength": "strong", "rationale": "r"}]}

    class FlakyAlerts(RecordingAlerts):
        def on_news_impacts(self, news, **kwargs):
            if news["id"] == first:
                raise RuntimeError("database is locked")
            return super().on_news_impacts(news, **kwargs)

    alerts = FlakyAlerts()
    _worker(FakeProvider(handle), alerts).do_cycle()
    assert [call["news"]["id"] for call in alerts.impacts] == [second]


def test_user_corrected_news_is_not_alerted() -> None:
    from app.services.ai.impact import replace_impacts_by_user

    news_id = _seed_news("Nvidia beats")
    with SessionLocal() as session:
        replace_impacts_by_user(session, news_id, [])
        session.commit()
    alerts = RecordingAlerts()
    _worker(FakeProvider(_handler(news_id)), alerts).do_cycle()
    assert alerts.impacts == []
