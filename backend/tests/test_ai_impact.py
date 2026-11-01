"""L2 精读：全文 → 中文摘要、明确看法、是否重大、结构化影响；用户修正落库并作为后续示例。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_ai import ImpactCorrection, NewsAiAnalysis, NewsAiScreen, NewsImpact
from app.models.news_item import NewsItem
from app.services.ai.context import PortfolioContext, WatchStock
from app.services.ai.impact import NewsImpactService, replace_impacts_by_user
from app.services.llm_providers import LLMProviderError

NOW = datetime(2031, 6, 3, 2, 0, tzinfo=UTC)
CONTEXT = PortfolioContext(
    stocks=(
        WatchStock(symbol="688256.SH", market="cn", name="寒武纪", is_holding=True),
        WatchStock(symbol="002384.SZ", market="cn", name="东山精密", is_holding=False),
    ),
    focus_sectors=("半导体",),
)


class FakeProvider:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, *, messages, response_format=None, operation_type="chat"):
        self.calls.append({"messages": messages, "operation_type": operation_type})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(content=json.dumps(response, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _clean():
    def wipe() -> None:
        with SessionLocal() as session:
            ids = list(session.scalars(select(NewsItem.id).where(NewsItem.source_name == "ai-impact-test")))
            for model in (ImpactCorrection, NewsImpact, NewsAiAnalysis, NewsAiScreen, ArticleContent):
                session.execute(delete(model).where(model.news_id.in_(ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(ids)))
            session.commit()

    wipe()
    yield
    wipe()


def _news(session, title: str, *, importance: int = 3, deep_read: bool = True, body: str | None = None,
          minutes_ago: int = 10, status: str = "ok") -> int:
    published = NOW - timedelta(minutes=minutes_ago)
    item = NewsItem(
        source_name="ai-impact-test",
        source_url="https://example.com/feed",
        title=title,
        summary=f"{title} summary",
        canonical_url=f"https://example.com/{title}",
        url_hash=f"ai-impact-{title}",
        market="us",
        published_at=published,
        fetched_at=published,
    )
    session.add(item)
    session.flush()
    session.add(NewsAiScreen(news_id=item.id, importance=importance, overseas=True, deep_read=deep_read,
                             status=status, attempts=1))
    if body:
        session.add(ArticleContent(news_id=item.id, content_text=body, extract_status="success"))
    session.flush()
    return item.id


def _service(session, provider, **overrides):
    options = {"daily_limit": 300, "min_importance": 2, "max_attempts": 3, "body_max_chars": 50,
               "correction_examples": 8}
    options.update(overrides)
    return NewsImpactService(session, provider, model_name="terra-test", clock=lambda: NOW, **options)


GOOD = {
    "summary_zh": "英伟达数据中心收入大增",
    "view": "利好 A 股 AI 芯片链，寒武纪受益",
    "major": True,
    "impacts": [
        {"target_type": "stock", "code": "688256", "name": "寒武纪", "direction": "bullish",
         "strength": "strong", "rationale": "国产替代预期"},
        {"target_type": "sector", "code": None, "name": "半导体", "direction": "bullish",
         "strength": "medium", "rationale": "需求外溢"},
        {"target_type": "stock", "code": "300308.SZ", "name": "中际旭创", "direction": "bullish",
         "strength": "strong", "rationale": "光模块"},
        {"target_type": "stock", "name": "坏数据", "direction": "up", "strength": "strong"},
    ],
}


def test_analyze_writes_analysis_and_validated_impacts() -> None:
    with SessionLocal() as session:
        news_id = _news(session, "Nvidia beats", body="B" * 200)
        session.commit()

    provider = FakeProvider([GOOD])
    with SessionLocal() as session:
        outcomes = _service(session, provider).analyze_pending(CONTEXT, limit=5)
        session.commit()
        assert [outcome.news.id for outcome in outcomes] == [news_id]
        outcome = outcomes[0]
        assert outcome.ok and outcome.analysis.major and outcome.analysis.view.startswith("利好")
        impacts = session.scalars(select(NewsImpact).where(NewsImpact.news_id == news_id)).all()
        assert [(i.target_type, i.target_code, i.target_name, i.direction, i.strength) for i in impacts] == [
            ("stock", "688256.SH", "寒武纪", "bullish", "strong"),  # 代码归一到自选股
            ("sector", None, "半导体", "bullish", "medium"),
            ("stock", "300308.SZ", "中际旭创", "bullish", "strong"),
        ]
        assert all(i.source == "ai" for i in impacts)

    call = provider.calls[0]
    assert call["operation_type"] == "ai_impact"
    prompt = call["messages"][1]["content"]
    assert "B" * 50 in prompt and "B" * 51 not in prompt  # 全文截断
    assert "寒武纪(688256.SH)" in prompt


def test_pending_order_filters_and_daily_limit() -> None:
    with SessionLocal() as session:
        low = _news(session, "low", importance=1)
        skip = _news(session, "skip", deep_read=False)
        failed_screen = _news(session, "failed-screen", status="error")
        second = _news(session, "second", importance=2, minutes_ago=1)
        first = _news(session, "first", importance=3, minutes_ago=30)
        session.add(NewsAiAnalysis(news_id=low, status="ok", attempts=1, analyzed_at=NOW - timedelta(hours=1)))
        session.commit()
        del skip, failed_screen

    with SessionLocal() as session:
        service = _service(session, FakeProvider([]))
        assert [item.id for item in service.pending_news(limit=10)] == [first, second]
        # 当天已精读 1 条，上限 2 → 只剩 1 条额度
        assert [item.id for item in _service(session, FakeProvider([]), daily_limit=2).pending_news(limit=10)] == [
            first
        ]


def test_failure_retries_then_reports_exhausted() -> None:
    with SessionLocal() as session:
        news_id = _news(session, "flaky")
        session.commit()

    provider = FakeProvider([LLMProviderError("timeout"), {"summary_zh": 1}, LLMProviderError("timeout")])
    with SessionLocal() as session:
        service = _service(session, provider)
        for attempt in (1, 2):
            outcome = service.analyze_pending(CONTEXT, limit=5)[0]
            session.commit()
            assert not outcome.ok and not outcome.exhausted
            row = session.scalar(select(NewsAiAnalysis).where(NewsAiAnalysis.news_id == news_id))
            assert row.status == "error" and row.attempts == attempt
        last = service.analyze_pending(CONTEXT, limit=5)[0]
        assert last.exhausted
        session.commit()
        assert service.analyze_pending(CONTEXT, limit=5) == []


def test_user_correction_replaces_impacts_and_feeds_next_prompt() -> None:
    with SessionLocal() as session:
        news_id = _news(session, "Micron guidance")
        other = _news(session, "SK Hynix capex", minutes_ago=30)
        session.commit()

    with SessionLocal() as session:
        _service(session, FakeProvider([GOOD])).analyze_pending(CONTEXT, limit=1)
        session.commit()
        replace_impacts_by_user(
            session,
            news_id,
            [{"target_type": "sector", "code": None, "name": "存储芯片", "direction": "bullish",
              "strength": "strong", "rationale": "美光指引上调直接映射国内存储"}],
            note="美光财报看存储，不看 AI 芯片",
        )
        session.commit()
        impacts = session.scalars(select(NewsImpact).where(NewsImpact.news_id == news_id)).all()
        assert [(i.target_name, i.source) for i in impacts] == [("存储芯片", "user")]
        correction = session.scalar(select(ImpactCorrection).where(ImpactCorrection.news_id == news_id))
        assert "寒武纪" in correction.before_json and "存储芯片" in correction.after_json

    provider = FakeProvider([GOOD])
    with SessionLocal() as session:
        outcomes = _service(session, provider).analyze_pending(CONTEXT, limit=1)
        assert outcomes[0].news.id == other
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "Micron guidance" in prompt and "存储芯片" in prompt and "美光财报看存储" in prompt


def test_user_correction_validates_payload() -> None:
    with SessionLocal() as session:
        news_id = _news(session, "validate")
        session.commit()
        with pytest.raises(ValueError):
            replace_impacts_by_user(session, news_id, [{"target_type": "stock", "name": "x", "direction": "up",
                                                       "strength": "strong"}])


def test_reanalysis_keeps_user_corrections() -> None:
    """用户先修正（哪怕改成"无影响"），之后的 L2 精读只更新文字结论，不覆盖影响、不再提醒。"""
    with SessionLocal() as session:
        news_id = _news(session, "corrected first")
        session.commit()
        replace_impacts_by_user(session, news_id, [], note="这条与我无关")
        session.commit()

    with SessionLocal() as session:
        [outcome] = _service(session, FakeProvider([GOOD])).analyze_pending(CONTEXT, limit=1)
        session.commit()
        assert outcome.ok and outcome.user_corrected and outcome.impacts == []
        assert session.scalars(select(NewsImpact).where(NewsImpact.news_id == news_id)).all() == []
        analysis = session.scalar(select(NewsAiAnalysis).where(NewsAiAnalysis.news_id == news_id))
        assert analysis.view.startswith("利好")


def test_user_correction_codes_are_normalized_to_watchlist_symbols() -> None:
    with SessionLocal() as session:
        news_id = _news(session, "normalize")
        session.commit()
        rows = replace_impacts_by_user(
            session, news_id,
            [{"target_type": "stock", "code": "688256", "name": "寒武纪", "direction": "bullish", "strength": "strong"}],
            context=CONTEXT,
        )
        assert rows[0].target_code == "688256.SH"
