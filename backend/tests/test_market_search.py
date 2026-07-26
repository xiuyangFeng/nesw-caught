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
        assert len(data) >= 2
        symbols = [item["symbol"] for item in data]
        assert "TCEHY" in symbols
        assert "0700.HK" in symbols


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
        assert any(item["symbol"] == "AAPL" for item in data)


def test_market_search_a_share_normalization_and_fallback() -> None:
    client = TestClient(app)

    # 1. 搜索大A中文名称/别名(如 五粮液)
    res = client.get("/api/market/search?q=五粮液")
    assert res.status_code == 200
    data = res.json()
    assert any(item["symbol"] == "000858.SZ" and item["market"] == "cn" for item in data)

    # 2. 搜索 Yahoo 返回 .SS 时，应自动规范化为 .SH
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": [
                {"symbol": "600519.SS", "shortname": "Kweichow Moutai", "exchange": "SHH", "quoteType": "EQUITY"}
            ]
        }
        mock_get.return_value = mock_response

        res = client.get("/api/market/search?q=600519")
        assert res.status_code == 200
        data = res.json()
        assert any(item["symbol"] == "600519.SH" and item["market"] == "cn" for item in data)

    # 3. 搜索 6 位纯数字大A代码(如 600900)，在离线或未预置时自动推导为 600900.SH
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = Exception("offline")
        res = client.get("/api/market/search?q=600900")
        assert res.status_code == 200
        data = res.json()
        assert any(item["symbol"] == "600900.SH" and item["market"] == "cn" for item in data)

