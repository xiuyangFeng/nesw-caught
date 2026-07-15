from datetime import UTC, datetime
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.quote_provider import (
    NormalizedSymbol,
    QuoteRecord,
    TencentQuoteProvider,
)
from app.services.quote_service import QuoteService


def test_tencent_quote_provider_parse_cn() -> None:
    provider = TencentQuoteProvider()
    ns = NormalizedSymbol(symbol="600519.SH", market="cn", provider_symbol="600519.SS")

    # Mock Tencent Response for CN stock
    mock_data = 'v_sh600519="1~贵州茅台~600519~1291.91~1279.00~1271.18~50495~24976~25519~1291.91~87~1291.90~1~1291.89~1~1291.88~42~1291.75~3~1292.00~11~1292.32~5~1292.33~1~1292.38~1~1292.40~6~~20260612154518~12.91~1.01~1295.00~1265.01~1291.91/50495/6477910214~50495~647791~0.40~19.52~~1295.00~1265.01~2.34~16149.93~16149.93~6.03~1406.90~1151.10~1.63~110~1282.89~14.82~19.62~~~0.33~647791.0214~0.0000~0~ ~GP-A~-6.19~1.50~4.00~30.53~26.78~1568.00~1250.10~-2.57~-3.08~-11.52~1250081601~1250081601~69.62~-12.77~1250081601~~~-8.21~0.04~~CNY~0~___D__F__N~1291.57~73~";'.encode("gbk")

    class FakeResponse:
        def __init__(self, data):
            self.data = data
        def read(self):
            return self.data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResponse(mock_data)):
        record = provider.fetch_quote(ns)
        assert record.symbol == "600519.SH"
        assert record.price == 1291.91
        assert record.previous_close == 1279.00
        assert record.open_price == 1271.18
        assert record.volume == 5049500  # 50495 * 100
        assert record.change_amount == 12.91
        assert record.change_percent == 1.01
        assert record.day_high == 1295.00
        assert record.day_low == 1265.01
        assert record.status == "ok"
        assert record.source == "tencent_finance"


def test_tencent_quote_provider_batch() -> None:
    provider = TencentQuoteProvider()
    ns1 = NormalizedSymbol(symbol="600519.SH", market="cn", provider_symbol="600519.SS")
    ns2 = NormalizedSymbol(symbol="0700.HK", market="hk", provider_symbol="0700.HK")

    mock_data = (
        'v_sh600519="1~贵州茅台~600519~1291.91~1279.00~1271.18~50495~24976~25519~1291.91~87~1291.90~1~1291.89~1~1291.88~42~1291.75~3~1292.00~11~1292.32~5~1292.33~1~1292.38~1~1292.40~6~~20260612154518~12.91~1.01~1295.00~1265.01~1291.91/50495/6477910214~50495~647791~0.40~19.52~~1295.00~1265.01~2.34~16149.93~16149.93~6.03~1406.90~1151.10~1.63~110~1282.89~14.82~19.62~~~0.33~647791.0214~0.0000~0~ ~GP-A~-6.19~1.50~4.00~30.53~26.78~1568.00~1250.10~-2.57~-3.08~-11.52~1250081601~1250081601~69.62~-12.77~1250081601~~~-8.21~0.04~~CNY~0~___D__F__N~1291.57~73~";\n'
        'v_hk00700="100~腾讯控股~00700~462.800~457.200~466.000~17788779.0~0~0~462.800~0~0~0~0~0~0~0~0~0~462.800~0~0~0~0~0~0~0~0~0~17788779.0~2026/06/12 15:30:45~5.600~1.22~467.000~459.400~462.800~17788779.0~8241691588.500~0~16.93~~0~0~1.66~42151.9787~42151.9787~TENCENT~1.15~677.700~420.400~0.60~4.05~0~0~0~0~0~15.83~3.33~0.20~100~-22.05~2.12~GP~20.59~11.53~8.33~1.74~-14.64~9108033432.00~9108033432.00~16.02~5.306~463.308~-27.48~HKD~1~30";'
    ).encode("gbk")

    class FakeResponse:
        def __init__(self, data):
            self.data = data
        def read(self):
            return self.data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResponse(mock_data)):
        records = provider.fetch_quotes_batch([ns1, ns2])
        assert len(records) == 2
        r1 = next(r for r in records if r.symbol == "600519.SH")
        r2 = next(r for r in records if r.symbol == "0700.HK")

        assert r1.price == 1291.91
        assert r2.price == 462.80
        assert r2.volume == 17788779


def test_quote_service_fallback_to_tencent() -> None:
    service = QuoteService()

    with SessionLocal() as session:
        session.query(WatchlistItem).filter(WatchlistItem.symbol == "600519.SH").delete()
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()

        session.add(WatchlistItem(symbol="600519.SH", market="cn", display_name="贵州茅台", is_active=True))
        session.commit()

        # Mock Yahoo Failure
        yahoo_fail_record = QuoteRecord(
            symbol="600519.SH",
            market="cn",
            provider_symbol="600519.SS",
            price=None,
            change_amount=None,
            change_percent=None,
            open_price=None,
            previous_close=None,
            day_high=None,
            day_low=None,
            volume=None,
            status="fetch_failed",
            source="yahoo_finance",
            message="Yahoo limit exceeded",
            fetched_at=datetime.now(UTC),
        )

        # Mock Tencent Success
        tencent_success_record = QuoteRecord(
            symbol="600519.SH",
            market="cn",
            provider_symbol="sh600519",
            price=1300.0,
            change_amount=21.0,
            change_percent=1.64,
            open_price=1280.0,
            previous_close=1279.0,
            day_high=1310.0,
            day_low=1275.0,
            volume=60000,
            status="ok",
            source="tencent_finance",
            message=None,
            fetched_at=datetime.now(UTC),
        )

        with patch.object(service.provider, "fetch_quotes_batch", return_value=[yahoo_fail_record]) as mock_yahoo, \
             patch.object(service.fallback_provider, "fetch_quotes_batch", return_value=[tencent_success_record]) as mock_tencent:

            payloads = service.refresh_watchlist_quotes(session)

            mock_yahoo.assert_called_once()
            mock_tencent.assert_called_once()

            row = next(item for item in payloads if item["symbol"] == "600519.SH")
            assert row["price"] == 1300.0
            assert row["status"] == "ok"
            assert row["source"] == "tencent_finance"

        # Cleanup
        session.query(WatchlistItem).filter(WatchlistItem.symbol == "600519.SH").delete()
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == "600519.SH").delete()
        session.commit()
