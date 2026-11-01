"""P3 接口：新闻 AI 结论、用户修正、个股影响、关注板块、漏斗状态。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.news_ai import ImpactCorrection, NewsAiAnalysis, NewsAiScreen, NewsImpact
from app.models.news_item import NewsItem
from app.models.sector import FocusSectorOverride, StockSector
from app.models.watchlist_item import WatchlistItem

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    def wipe() -> None:
        with SessionLocal() as session:
            ids = list(session.scalars(select(NewsItem.id).where(NewsItem.source_name == "ai-api-test")))
            for model in (ImpactCorrection, NewsImpact, NewsAiAnalysis, NewsAiScreen):
                session.execute(delete(model).where(model.news_id.in_(ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(ids)))
            session.execute(delete(StockSector))
            session.execute(delete(FocusSectorOverride))
            session.execute(delete(WatchlistItem))
            session.commit()

    wipe()
    yield
    wipe()


def _seed(title: str = "Nvidia beats", *, minutes_ago: int = 5, with_ai: bool = True) -> int:
    with SessionLocal() as session:
        published = datetime.now(UTC) - timedelta(minutes=minutes_ago)
        item = NewsItem(source_name="ai-api-test", source_url="https://example.com", title=title,
                        canonical_url=f"https://example.com/{title}", url_hash=f"ai-api-{title}", market="us",
                        published_at=published, fetched_at=published)
        session.add(item)
        session.flush()
        if with_ai:
            session.add(NewsAiScreen(news_id=item.id, importance=3, overseas=True, deep_read=True,
                                     title_zh="英伟达业绩超预期", reason="r", status="ok", attempts=1))
            session.add(NewsAiAnalysis(news_id=item.id, summary_zh="摘要", view="利好寒武纪", major=True,
                                       status="ok", attempts=1))
            session.add(NewsImpact(news_id=item.id, target_type="stock", target_code="688256.SH",
                                   target_name="寒武纪", direction="bullish", strength="strong", rationale="需求"))
        session.commit()
        return item.id


def test_get_news_ai_returns_screen_analysis_and_impacts() -> None:
    news_id = _seed()
    data = client.get(f"/api/news/{news_id}/ai").json()
    assert data["news_id"] == news_id
    assert data["screen"]["importance"] == 3 and data["screen"]["title_zh"] == "英伟达业绩超预期"
    assert data["analysis"]["view"] == "利好寒武纪" and data["analysis"]["major"] is True
    assert data["impacts"] == [
        {"id": data["impacts"][0]["id"], "target_type": "stock", "code": "688256.SH", "name": "寒武纪",
         "direction": "bullish", "strength": "strong", "rationale": "需求", "source": "ai"}
    ]


def test_get_news_ai_without_results_returns_nulls_and_404_for_missing_news() -> None:
    news_id = _seed("plain", with_ai=False)
    data = client.get(f"/api/news/{news_id}/ai").json()
    assert data == {"news_id": news_id, "screen": None, "analysis": None, "impacts": []}
    assert client.get("/api/news/99999999/ai").status_code == 404


def test_put_impacts_records_correction() -> None:
    news_id = _seed()
    response = client.put(
        f"/api/news/{news_id}/impacts",
        json={"impacts": [{"target_type": "sector", "code": None, "name": "存储芯片", "direction": "bullish",
                           "strength": "medium", "rationale": "映射"}], "note": "看存储"},
    )
    assert response.status_code == 200
    assert [(i["name"], i["source"]) for i in response.json()["impacts"]] == [("存储芯片", "user")]
    with SessionLocal() as session:
        correction = session.scalar(select(ImpactCorrection).where(ImpactCorrection.news_id == news_id))
        assert correction.note == "看存储"

    bad = client.put(f"/api/news/{news_id}/impacts",
                     json={"impacts": [{"target_type": "stock", "name": "x", "direction": "up", "strength": "strong"}]})
    assert bad.status_code == 422
    assert client.put("/api/news/99999999/impacts", json={"impacts": []}).status_code == 404


def test_watchlist_symbol_impacts_lists_recent_news_impacts() -> None:
    news_id = _seed()
    old_id = _seed("old one", minutes_ago=60)
    data = client.get("/api/watchlist/688256.SH/impacts").json()
    assert [row["news_id"] for row in data] == [news_id, old_id]
    assert data[0]["title_zh"] == "英伟达业绩超预期" and data[0]["direction"] == "bullish"
    assert client.get("/api/watchlist/688256.SH/impacts?limit=1").json()[0]["news_id"] == news_id


def test_focus_sectors_crud() -> None:
    with SessionLocal() as session:
        session.add(WatchlistItem(symbol="688256.SH", market="cn", display_name="寒武纪"))
        session.add(StockSector(symbol="688256.SH", sector="半导体", source="ai"))
        session.commit()

    assert client.get("/api/focus-sectors").json() == [{"name": "半导体", "source": "ai", "symbols": ["688256.SH"]}]
    assert client.post("/api/focus-sectors", json={"name": "光模块"}).status_code == 201
    assert client.post("/api/focus-sectors", json={"name": "  "}).status_code == 422
    assert client.delete("/api/focus-sectors/半导体").status_code == 204
    assert [s["name"] for s in client.get("/api/focus-sectors").json()] == ["光模块"]


def test_funnel_status_endpoint() -> None:
    data = client.get("/api/ai/funnel/status").json()
    assert set(data) >= {"enabled", "active", "inactive_reason", "model_name", "today", "usage", "last_error"}
    assert {entry["operation_type"] for entry in data["usage"]} == {"ai_screen", "ai_impact", "sector_infer"}
