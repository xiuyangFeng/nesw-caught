"""市场总览 API 测试（计划任务 B6）。

覆盖：
- GET /api/market/overview：五市场固定骨架、空配置回落默认清单、板块 source
  按市场分流（cn=eastmoney / us,eu=preset_etf / kr,jp=none）、^VIX 不在指数行
  但进入 quant_sentiment.inputs.vix、新闻情绪 insufficient_data 分支、
  量化情绪 unknown 降级、快照数据进入指数行与量化情绪
- 配置 CRUD：创建 201、重复 (symbol, market) 409、非法 market/kind/空 symbol 400、
  PATCH 禁改 symbol/market（请求模型拒绝）、PATCH 白名单更新、DELETE 204 后 404
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes import market as market_routes
from app.db.session import SessionLocal
from app.main import app
from app.models.market_index_config import MarketIndexConfig
from app.models.price_snapshot import PriceSnapshot
from app.services.board_provider import BoardFetchResult, BoardQuote

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_tables():
    with SessionLocal() as session:
        session.query(MarketIndexConfig).delete()
        session.query(PriceSnapshot).delete()
        session.commit()
    yield


@pytest.fixture(autouse=True)
def _stub_boards(monkeypatch):
    """板块缓存为空时 overview 会同步触发东财抓取；测试一律 stub 掉，不碰外网。"""
    result = BoardFetchResult(status="fetch_failed", stale=False, items=[], message="stubbed")
    monkeypatch.setattr(market_routes, "get_cached_industry_boards", lambda **kwargs: result)
    return result


def _ok_board_result() -> BoardFetchResult:
    now = datetime.now(UTC)
    return BoardFetchResult(
        status="ok",
        stale=False,
        items=[
            BoardQuote(
                code="BK0420",
                name="航天航空",
                price=1234.56,
                change_percent=2.35,
                advance_count=30,
                decline_count=5,
                flat_count=2,
                net_inflow=1.5e8,
                fetched_at=now,
            ),
            BoardQuote(
                code="BK0445",
                name="酿酒行业",
                price=2345.67,
                change_percent=-1.2,
                advance_count=4,
                decline_count=25,
                flat_count=1,
                net_inflow=-2.3e7,
                fetched_at=now,
            ),
        ],
        fetched_at=now,
    )


def _seed_snapshot(symbol: str, market: str, price: float, change_percent: float) -> None:
    with SessionLocal() as session:
        session.add(
            PriceSnapshot(
                symbol=symbol,
                market=market,
                price=price,
                change_amount=price * change_percent / 100,
                change_percent=change_percent,
                open_price=price - 1,
                previous_close=price / (1 + change_percent / 100),
                day_high=price + 1,
                day_low=price - 2,
                volume=None,
                provider_name="yahoo_finance",
                provider_symbol=symbol,
                quote_status="ok",
                status_message=None,
                fetched_at=datetime.now(UTC),
            )
        )
        session.commit()


def _markets_by_key(payload: dict) -> dict[str, dict]:
    return {market["market"]: market for market in payload["markets"]}


# ---------------------------------------------------------------------------
# GET /api/market/overview
# ---------------------------------------------------------------------------


def test_overview_returns_five_market_skeleton_with_default_configs() -> None:
    response = client.get("/api/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"]
    markets = _markets_by_key(payload)
    assert list(payload["markets"][i]["market"] for i in range(5)) == ["us", "cn", "kr", "jp", "eu"]
    assert set(markets) == {"us", "cn", "kr", "jp", "eu"}

    us = markets["us"]
    assert us["display_name"] == "美股"
    assert us["is_open"] in (True, False)
    us_symbols = [idx["symbol"] for idx in us["indices"]]
    # ^VIX 不在指数行展示（仅情绪计算）。
    assert "^GSPC" in us_symbols
    assert "^IXIC" in us_symbols
    assert "^VIX" not in us_symbols
    # 无快照时指数行 status=unavailable 占位。
    assert all(idx["status"] == "unavailable" for idx in us["indices"])
    assert all(idx["price"] is None for idx in us["indices"])

    # 板块区 source 按市场分流。
    assert markets["cn"]["boards"]["source"] == "eastmoney"
    assert markets["us"]["boards"]["source"] == "preset_etf"
    assert markets["eu"]["boards"]["source"] == "preset_etf"
    assert markets["kr"]["boards"] == {
        "status": "none",
        "stale": False,
        "source": "none",
        "items": [],
        "message": None,
    }
    assert markets["jp"]["boards"]["source"] == "none"
    # preset_etf 板块区列出配置表 kind=etf 条目（默认清单含 XLK）。
    us_etf_codes = [item["code"] for item in markets["us"]["boards"]["items"]]
    assert "XLK" in us_etf_codes

    # 无新闻时新闻情绪 insufficient_data；无快照时量化情绪 unknown。
    for market in markets.values():
        assert market["news_sentiment"]["status"] == "insufficient_data"
        assert market["news_sentiment"]["score"] is None
        assert market["quant_sentiment"]["label"] == "unknown"
        assert market["quant_sentiment"]["score"] is None


def test_overview_uses_snapshots_and_computes_quant_sentiment(monkeypatch) -> None:
    monkeypatch.setattr(
        market_routes, "get_cached_industry_boards", lambda **kwargs: _ok_board_result()
    )
    _seed_snapshot("^GSPC", "us", 6450.12, 0.82)
    _seed_snapshot("^IXIC", "us", 21400.5, 1.1)
    _seed_snapshot("^VIX", "us", 14.2, -3.0)
    _seed_snapshot("XLK", "us", 280.0, 1.2)
    _seed_snapshot("000300.SS", "cn", 4100.0, -0.4)

    response = client.get("/api/market/overview")

    assert response.status_code == 200
    markets = _markets_by_key(response.json())

    us = markets["us"]
    gspc = next(idx for idx in us["indices"] if idx["symbol"] == "^GSPC")
    assert gspc["display_name"] == "标普500"
    assert gspc["kind"] == "index"
    assert gspc["price"] == pytest.approx(6450.12)
    assert gspc["change_percent"] == pytest.approx(0.82)
    assert gspc["status"] == "ok"
    assert gspc["fetched_at"]

    # 量化情绪：动量 avg=(0.82+1.1)/2=0.96（^VIX 不计入动量），VIX=14.2 参与。
    quant = us["quant_sentiment"]
    assert quant["inputs"]["avg_change_percent"] == pytest.approx(0.96)
    assert quant["inputs"]["vix"] == pytest.approx(14.2)
    assert quant["inputs"]["adv_ratio"] is None
    assert quant["label"] in {"panic", "fear", "neutral", "greed", "greed_extreme"}
    assert quant["score"] is not None

    # cn：东财板块榜 + 涨跌家数进入量化情绪 adv_ratio=(30+4)/(30+5+2+4+25+1)。
    cn = markets["cn"]
    assert cn["boards"]["status"] == "ok"
    assert cn["boards"]["stale"] is False
    assert [item["code"] for item in cn["boards"]["items"]] == ["BK0420", "BK0445"]
    first = cn["boards"]["items"][0]
    assert first["name"] == "航天航空"
    assert first["change_percent"] == pytest.approx(2.35)
    assert first["advance_count"] == 30
    assert cn["quant_sentiment"]["inputs"]["adv_ratio"] == pytest.approx(34 / 67)
    # 000001.SS 无快照不参与平均，avg 即 000300.SS 的 -0.4。
    assert cn["quant_sentiment"]["inputs"]["avg_change_percent"] == pytest.approx(-0.4)

    # us 板块区 ETF 行带快照数据。
    xlk = next(item for item in us["boards"]["items"] if item["code"] == "XLK")
    assert xlk["name"] == "科技ETF"
    assert xlk["change_percent"] == pytest.approx(1.2)


def test_overview_empty_config_market_returns_empty_indices() -> None:
    # 配置表非空时不再回落默认清单：只配了 kr，其它市场 indices 为空骨架。
    with SessionLocal() as session:
        session.add(
            MarketIndexConfig(symbol="^KS11", market="kr", display_name="韩国KOSPI", kind="index")
        )
        session.commit()

    response = client.get("/api/market/overview")

    assert response.status_code == 200
    markets = _markets_by_key(response.json())
    assert [idx["symbol"] for idx in markets["kr"]["indices"]] == ["^KS11"]
    assert markets["us"]["indices"] == []
    assert markets["cn"]["indices"] == []
    assert markets["us"]["boards"]["items"] == []


# ---------------------------------------------------------------------------
# 配置 CRUD
# ---------------------------------------------------------------------------


def test_index_config_crud_full_cycle() -> None:
    create = client.post(
        "/api/market/index-config",
        json={"symbol": " ^ftse ", "market": "EU", "display_name": "富时100", "sort_order": 3},
    )
    assert create.status_code == 201
    created = create.json()
    assert created["symbol"] == "^FTSE"  # 去空白大写
    assert created["market"] == "eu"  # market 归一小写
    assert created["kind"] == "index"
    assert created["sort_order"] == 3
    assert created["enabled"] is True
    config_id = created["id"]

    listed = client.get("/api/market/index-config")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [config_id]

    patch = client.patch(
        f"/api/market/index-config/{config_id}",
        json={"display_name": "英国富时100", "sort_order": 1, "enabled": False, "kind": "etf"},
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["display_name"] == "英国富时100"
    assert patched["sort_order"] == 1
    assert patched["enabled"] is False
    assert patched["kind"] == "etf"
    assert patched["symbol"] == "^FTSE"
    assert patched["market"] == "eu"

    delete = client.delete(f"/api/market/index-config/{config_id}")
    assert delete.status_code == 204
    assert client.get("/api/market/index-config").json() == []


def test_index_config_create_duplicate_returns_409() -> None:
    payload = {"symbol": "^GSPC", "market": "us", "display_name": "标普500"}
    assert client.post("/api/market/index-config", json=payload).status_code == 201

    duplicate = client.post("/api/market/index-config", json=payload)

    assert duplicate.status_code == 409


def test_index_config_create_validation_errors() -> None:
    bad_market = client.post(
        "/api/market/index-config",
        json={"symbol": "^GSPC", "market": "hk", "display_name": "非法市场"},
    )
    assert bad_market.status_code == 400

    blank_symbol = client.post(
        "/api/market/index-config",
        json={"symbol": "   ", "market": "us", "display_name": "空代码"},
    )
    assert blank_symbol.status_code == 400

    blank_name = client.post(
        "/api/market/index-config",
        json={"symbol": "^GSPC", "market": "us", "display_name": "  "},
    )
    assert blank_name.status_code == 400

    bad_kind = client.post(
        "/api/market/index-config",
        json={"symbol": "^GSPC", "market": "us", "display_name": "标普500", "kind": "stock"},
    )
    assert bad_kind.status_code == 400


def test_index_config_patch_rejects_symbol_and_market() -> None:
    create = client.post(
        "/api/market/index-config",
        json={"symbol": "^GSPC", "market": "us", "display_name": "标普500"},
    )
    config_id = create.json()["id"]

    # 请求模型不含 symbol/market 字段（extra=forbid）：传了就 422，语义上禁改。
    patch = client.patch(
        f"/api/market/index-config/{config_id}", json={"symbol": "^IXIC"}
    )
    assert patch.status_code == 422
    patch_market = client.patch(
        f"/api/market/index-config/{config_id}", json={"market": "cn"}
    )
    assert patch_market.status_code == 422

    unchanged = client.get("/api/market/index-config").json()[0]
    assert unchanged["symbol"] == "^GSPC"
    assert unchanged["market"] == "us"


def test_index_config_patch_and_delete_missing_id_return_404() -> None:
    assert client.patch("/api/market/index-config/9999", json={"sort_order": 1}).status_code == 404
    assert client.delete("/api/market/index-config/9999").status_code == 404
