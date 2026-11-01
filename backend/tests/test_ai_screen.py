"""L1 粗筛：标题+摘要批量判断重要度、是否海外、是否精读、译文标题。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.news_ai import NewsAiScreen
from app.models.news_item import NewsItem
from app.services.ai.context import PortfolioContext, WatchStock
from app.services.ai.screen import NewsScreenService
from app.services.llm_providers import LLMProviderError

NOW = datetime(2031, 6, 3, 2, 0, tzinfo=UTC)  # 远离其他测试的种子新闻，避免落进 24h 窗口
CONTEXT = PortfolioContext(
    stocks=(WatchStock(symbol="688256.SH", market="cn", name="寒武纪", is_holding=True),),
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
        if callable(response):
            response = response(messages)
        return SimpleNamespace(content=json.dumps(response, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _clean():
    def wipe() -> None:
        with SessionLocal() as session:
            session.execute(delete(NewsAiScreen))
            session.execute(delete(NewsItem).where(NewsItem.source_name == "ai-screen-test"))
            session.commit()

    wipe()
    yield
    wipe()


def _news(session, title: str, *, hours_ago: float = 1, summary: str | None = None, market: str = "us") -> int:
    published = NOW - timedelta(hours=hours_ago)
    item = NewsItem(
        source_name="ai-screen-test",
        source_url="https://example.com/feed",
        title=title,
        summary=summary,
        canonical_url=f"https://example.com/{title}",
        url_hash=f"ai-screen-{title}",
        market=market,
        published_at=published,
        fetched_at=published,
        effective_at=published,
    )
    session.add(item)
    session.flush()
    return item.id


def _service(session, provider, **overrides):
    options = {"batch_size": 20, "lookback_hours": 24, "max_attempts": 3}
    options.update(overrides)
    return NewsScreenService(session, provider, model_name="terra-test", clock=lambda: NOW, **options)


def test_screen_batch_writes_rows_and_sends_context() -> None:
    with SessionLocal() as session:
        nvda = _news(session, "Nvidia beats estimates", summary="Data center revenue soars")
        noise = _news(session, "本地天气晴", market="cn")
        session.commit()

    provider = FakeProvider(
        [
            {
                "items": [
                    {"id": nvda, "importance": 3, "overseas": True, "deep_read": True,
                     "title_zh": "英伟达业绩超预期", "reason": "AI 芯片需求，影响寒武纪"},
                    {"id": noise, "importance": 0, "overseas": False, "deep_read": False,
                     "title_zh": None, "reason": "无关"},
                ]
            }
        ]
    )
    with SessionLocal() as session:
        outcome = _service(session, provider).screen_once(CONTEXT)
        session.commit()
        assert outcome.screened == 2 and outcome.failed == 0 and outcome.exhausted == []
        rows = {row.news_id: row for row in session.scalars(select(NewsAiScreen))}
        assert rows[nvda].importance == 3 and rows[nvda].overseas and rows[nvda].deep_read
        assert rows[nvda].title_zh == "英伟达业绩超预期"
        assert rows[nvda].status == "ok" and rows[nvda].model_name == "terra-test"
        assert rows[noise].importance == 0 and rows[noise].title_zh is None

    call = provider.calls[0]
    assert call["operation_type"] == "ai_screen"
    user_prompt = call["messages"][1]["content"]
    assert "寒武纪(688256.SH)" in user_prompt and "半导体" in user_prompt
    assert f"[{nvda}]" in user_prompt and "Data center revenue soars" in user_prompt


def test_screen_skips_old_and_already_screened_news() -> None:
    with SessionLocal() as session:
        old = _news(session, "old news", hours_ago=30)
        done = _news(session, "done news")
        fresh = _news(session, "fresh news")
        session.add(NewsAiScreen(news_id=done, importance=1, overseas=False, deep_read=False, status="ok", attempts=1))
        session.commit()

    def answer(messages):
        prompt = messages[1]["content"]
        assert f"[{old}]" not in prompt and f"[{done}]" not in prompt
        return {"items": [{"id": fresh, "importance": 1, "overseas": True, "deep_read": False, "reason": "r"}]}

    provider = FakeProvider([answer])
    with SessionLocal() as session:
        outcome = _service(session, provider).screen_once(CONTEXT)
    assert outcome.screened == 1


def test_invalid_or_missing_items_fail_individually_and_retry_until_exhausted() -> None:
    with SessionLocal() as session:
        good = _news(session, "good")
        missing = _news(session, "missing")
        broken = _news(session, "broken")
        session.commit()

    batch = {
        "items": [
            {"id": good, "importance": 2, "overseas": False, "deep_read": True, "reason": "ok"},
            {"id": broken, "importance": 9, "overseas": False, "deep_read": True},
            {"id": 999999, "importance": 3, "overseas": True, "deep_read": True},
        ]
    }
    provider = FakeProvider([batch, LLMProviderError("timeout"), LLMProviderError("timeout")])
    with SessionLocal() as session:
        service = _service(session, provider)
        first = service.screen_once(CONTEXT)
        session.commit()
        assert first.screened == 1 and first.failed == 2 and first.exhausted == []
        rows = {row.news_id: row for row in session.scalars(select(NewsAiScreen))}
        assert rows[missing].status == "error" and rows[missing].attempts == 1
        assert rows[broken].status == "error"

        second = service.screen_once(CONTEXT)  # 整批失败：两条各 +1
        session.commit()
        assert second.failed == 2 and second.exhausted == []
        third = service.screen_once(CONTEXT)
        session.commit()
        assert sorted(third.exhausted) == sorted([missing, broken])
        assert service.screen_once(CONTEXT).screened == 0  # 用尽后不再重试
        assert len(provider.calls) == 3
