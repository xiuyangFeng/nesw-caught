"""A 股个股资金流按需服务测试（聚焦改造 P1-T1）。

覆盖：
- 东财 fflow/daykline 字段顺序：f52 主力、f53 小单、f54 中单、f55 大单、f56 超大单、f57 主力净占比
  （实测：主力净流入 = 大单 + 超大单）
- secid 映射（SH→1.，SZ/BJ→0.）
- 非 A 股、上游失败均返回空 points + note，不抛异常
- TTL 内同一标的只请求上游一次
- GET /api/market/symbols/{symbol}/fund-flow 响应结构
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import fund_flow_service
from app.services.fund_flow_service import (
    FundFlowService,
    parse_fund_flow_payload,
    secid_for_symbol,
)

# 2026-10-30 东山精密真实返回（截取前 7 列）：主力 = 大单(-403589328) + 超大单(-122701296)
REAL_ROW = "2026-10-30,-526290624.0,622399088.0,-96108480.0,-403589328.0,-122701296.0,-7.29"


def _payload(*rows: str) -> dict:
    return {"data": {"klines": list(rows)}}


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, payload: object = None, *, error: Exception | None = None) -> None:
        self.payload = payload if payload is not None else _payload(REAL_ROW)
        self.error = error
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.error is not None:
            raise self.error
        return _FakeResponse(self.payload)


def test_parse_uses_eastmoney_column_order() -> None:
    rows = parse_fund_flow_payload("002384.sz", _payload(REAL_ROW, "bad-row"))

    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == "002384.SZ"
    assert row.trade_date == date(2026, 10, 30)
    assert row.main_net_inflow == -526290624.0
    assert row.small_net == 622399088.0
    assert row.medium_net == -96108480.0
    assert row.large_net == -403589328.0
    assert row.super_large_net == -122701296.0
    assert row.main_net_pct == -7.29
    # 东财口径：主力 = 大单 + 超大单
    assert row.large_net + row.super_large_net == pytest.approx(row.main_net_inflow)


def test_secid_maps_exchanges() -> None:
    assert secid_for_symbol("600519.SH") == "1.600519"
    assert secid_for_symbol("300750.SZ") == "0.300750"
    assert secid_for_symbol("830799.BJ") == "0.830799"


def test_non_a_share_returns_note_without_fetch() -> None:
    client = _FakeClient()
    view = FundFlowService(client=client).get_fund_flow("9988.HK")

    assert view.symbol == "9988.HK"
    assert view.points == []
    assert view.note
    assert client.calls == []


def test_upstream_failure_returns_note() -> None:
    client = _FakeClient(error=RuntimeError("boom"))
    view = FundFlowService(client=client).get_fund_flow("002384.SZ")

    assert view.points == []
    assert view.note


def test_limits_to_recent_points_in_ascending_order() -> None:
    rows = [f"2026-{m:02d}-{d:02d},1,1,1,1,1,1" for m in (8, 9, 10) for d in range(1, 29)]
    client = _FakeClient(_payload(*rows))
    view = FundFlowService(client=client, max_points=60).get_fund_flow("600519.SH")

    assert len(view.points) == 60
    assert view.points[0].trade_date < view.points[-1].trade_date
    assert view.points[-1].trade_date == date(2026, 10, 28)


def test_ttl_cache_hits_upstream_once() -> None:
    client = _FakeClient()
    service = FundFlowService(client=client, ttl_seconds=600)

    first = service.get_fund_flow("002384.SZ")
    second = service.get_fund_flow("002384.sz")

    assert first == second
    assert len(client.calls) == 1


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_failures_are_cached_briefly_then_retried() -> None:
    """东财限流时短时间内不重复打上游；失败缓存远短于成功缓存，过期后重试。"""
    clock = _Clock()
    client = _FakeClient(error=RuntimeError("boom"))
    service = FundFlowService(client=client, ttl_seconds=600, failure_ttl_seconds=60, clock=clock)

    first = service.get_fund_flow("002384.SZ")
    clock.now += 30
    second = service.get_fund_flow("002384.SZ")

    assert first.points == [] and second.points == []
    assert second.note
    assert len(client.calls) == 1

    client.error = None
    clock.now += 31
    recovered = service.get_fund_flow("002384.SZ")

    assert len(recovered.points) == 1
    assert len(client.calls) == 2


def test_success_cache_expires_after_ttl() -> None:
    clock = _Clock()
    client = _FakeClient()
    service = FundFlowService(client=client, ttl_seconds=600, clock=clock)

    service.get_fund_flow("002384.SZ")
    clock.now += 601
    service.get_fund_flow("002384.SZ")

    assert len(client.calls) == 2


def test_route_returns_fund_flow_view(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FundFlowService(client=_FakeClient())
    monkeypatch.setattr(fund_flow_service, "get_fund_flow_service", lambda: service)

    response = TestClient(app).get("/api/market/symbols/002384.SZ/fund-flow")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "002384.SZ"
    assert body["note"] is None
    assert body["points"] == [
        {
            "trade_date": "2026-10-30",
            "main_net_inflow": -526290624.0,
            "super_large_net": -122701296.0,
            "large_net": -403589328.0,
            "medium_net": -96108480.0,
            "small_net": 622399088.0,
            "main_net_pct": -7.29,
        }
    ]
