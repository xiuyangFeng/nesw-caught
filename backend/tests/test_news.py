from fastapi.testclient import TestClient

from app.main import app


def test_news_list_applies_filters_and_limit() -> None:
    client = TestClient(app)

    response = client.get("/api/news", params={"market": "hk", "source_name": "Reuters", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["market"] == "hk"
    assert payload[0]["source_name"] == "Reuters"


def test_news_list_applies_keyword_filter() -> None:
    client = TestClient(app)

    response = client.get("/api/news", params={"q": "Tencent"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert "Tencent" in payload[0]["title"]


def test_news_detail_serializes_utc_timestamps() -> None:
    client = TestClient(app)

    response = client.get("/api/news/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["published_at"].endswith("Z")
    assert payload["fetched_at"].endswith("Z")
    assert payload["article"]["extracted_at"].endswith("Z")
