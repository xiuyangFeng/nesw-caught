from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.price_snapshot import PriceSnapshot


def test_market_search_online() -> None:
    client = TestClient(app)

    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": [
                {"symbol": "TCEHY", "shortname": "Tencent Holdings ADR", "exchange": "PNK", "quoteType": "EQUITY"},
                {"symbol": "0700.HK", "shortname": "Tencent Holdings Ltd", "exchange": "HKG", "quoteType": "EQUITY"}
            ]
        }
        mock_get.return_value = mock_response

        res = client.get("/api/market/search?q=Tencent")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "TCEHY"
        assert data[0]["market"] == "us"
        assert data[1]["symbol"] == "0700.HK"
        assert data[1]["market"] == "hk"


def test_market_search_offline_fallback() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        session.query(PriceSnapshot).delete()
        snapshot = PriceSnapshot(
            symbol="AAPL",
            market="us",
            price=150.0,
            volume=1000,
            provider_name="yahoo",
            provider_symbol="AAPL",
            quote_status="ok",
            fetched_at=datetime.now(UTC),
        )
        session.add(snapshot)
        session.commit()

    with patch("httpx.get") as mock_get:
        mock_get.side_effect = Exception("network offline")

        res = client.get("/api/market/search?q=AA")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"
        assert data[0]["market"] == "us"
