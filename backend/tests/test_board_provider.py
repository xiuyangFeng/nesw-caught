"""EastMoneyBoardProvider 单元测试。

全部通过 mock httpx 响应（monkeypatch ``app.services.http_pool.get_feed_client``），
不真实请求外网。覆盖：正常解析、字段缺失容错、结构异常、HTTP 失败、
TTL 缓存命中、stale 降级与无缓存空态。
"""

from __future__ import annotations

import httpx
import pytest

from app.services.board_provider import (
    MARKET_BOARD_CACHE_TTL_SECONDS,
    EastMoneyBoardProvider,
    clear_board_cache,
    get_cached_industry_boards,
)


@pytest.fixture(autouse=True)
def _reset_board_cache():
    clear_board_cache()
    yield
    clear_board_cache()


_SAMPLE_PAYLOAD = {
    "rc": 0,
    "rt": 17,
    "data": {
        "total": 2,
        "diff": [
            {
                "f12": "BK0420",
                "f14": "航天航空",
                "f2": 1234.56,
                "f3": 2.35,
                "f104": 30,
                "f105": 5,
                "f106": 2,
                "f62": 123456789.0,
            },
            {
                "f12": "BK0475",
                "f14": "银行",
                "f2": 3210.1,
                "f3": -0.85,
                "f104": 8,
                "f105": 30,
                "f106": 4,
                "f62": -98765432.0,
            },
        ],
    },
}


def _make_response(status_code: int = 200, payload: object | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://push2.eastmoney.com/api/qt/clist/get")
    return httpx.Response(status_code, json=payload, request=request)


class _FakeClient:
    """记录调用次数的可编程假 client。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses: list[object] = []

    def queue(self, item: object) -> None:
        self.responses.append(item)

    def get(self, url: str, **kwargs):  # noqa: ANN001 - 对齐 httpx.Client.get 签名子集
        self.calls.append({"url": url, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("unexpected extra http call")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install_client(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> _FakeClient:
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: client)
    return client


def _queued_ok_client(monkeypatch: pytest.MonkeyPatch, payload: object = _SAMPLE_PAYLOAD) -> _FakeClient:
    client = _FakeClient()
    client.queue(_make_response(200, payload))
    return _install_client(monkeypatch, client)


def test_fetch_industry_boards_parses_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _queued_ok_client(monkeypatch)
    provider = EastMoneyBoardProvider()

    boards = provider.fetch_industry_boards(limit=20)

    assert len(boards) == 2
    first = boards[0]
    assert first.code == "BK0420"
    assert first.name == "航天航空"
    assert first.price == pytest.approx(1234.56)
    assert first.change_percent == pytest.approx(2.35)
    assert first.advance_count == 30
    assert first.decline_count == 5
    assert first.flat_count == 2
    assert first.net_inflow == pytest.approx(123456789.0)
    assert first.fetched_at is not None

    second = boards[1]
    assert second.code == "BK0475"
    assert second.change_percent == pytest.approx(-0.85)
    assert second.net_inflow == pytest.approx(-98765432.0)


def test_fetch_industry_boards_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _queued_ok_client(monkeypatch)
    provider = EastMoneyBoardProvider()

    provider.fetch_industry_boards(limit=10)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://push2.eastmoney.com/api/qt/clist/get"
    params = call["kwargs"]["params"]
    # 行业板块（m:90+t:2），按涨跌幅排序
    assert params["fs"] == "m:90+t:2"
    assert params["fid"] == "f3"
    fields = set(params["fields"].split(","))
    assert {"f12", "f14", "f2", "f3", "f104", "f105", "f106", "f62"} <= fields
    headers = call["kwargs"]["headers"]
    assert headers["Referer"] == "https://quote.eastmoney.com/"
    assert call["kwargs"]["timeout"] == 5.0


def test_fetch_industry_boards_respects_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _queued_ok_client(monkeypatch)
    provider = EastMoneyBoardProvider()

    boards = provider.fetch_industry_boards(limit=1)

    assert len(boards) == 1
    assert boards[0].code == "BK0420"


def test_fetch_industry_boards_tolerates_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "rc": 0,
        "data": {
            "total": 3,
            "diff": [
                {
                    "f12": "BK0001",
                    "f14": "缺失字段板块",
                    "f2": "-",
                    "f3": "-",
                    "f104": "-",
                    # f105/f106/f62 整体缺失
                },
                # 无 f12 代码的条目应被跳过
                {"f14": "无名板块", "f3": 1.0},
                {"f12": "BK0002", "f14": "正常板块", "f3": "1.5", "f104": "10"},
            ],
        },
    }
    _queued_ok_client(monkeypatch, payload)
    provider = EastMoneyBoardProvider()

    boards = provider.fetch_industry_boards()

    assert [b.code for b in boards] == ["BK0001", "BK0002"]
    broken = boards[0]
    assert broken.price is None
    assert broken.change_percent is None
    assert broken.advance_count is None
    assert broken.decline_count is None
    assert broken.flat_count is None
    assert broken.net_inflow is None
    # 字符串数字可被容错解析
    assert boards[1].change_percent == pytest.approx(1.5)
    assert boards[1].advance_count == 10


def test_fetch_industry_boards_raises_when_diff_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _queued_ok_client(monkeypatch, {"rc": 0, "data": None})
    provider = EastMoneyBoardProvider()

    with pytest.raises(RuntimeError):
        provider.fetch_industry_boards()


def test_fetch_industry_boards_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    client.queue(httpx.ConnectError("connection refused"))
    _install_client(monkeypatch, client)
    provider = EastMoneyBoardProvider()

    with pytest.raises(RuntimeError):
        provider.fetch_industry_boards()


def test_fetch_industry_boards_raises_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    client.queue(_make_response(429, {"rc": -1}))
    _install_client(monkeypatch, client)
    provider = EastMoneyBoardProvider()

    with pytest.raises(RuntimeError):
        provider.fetch_industry_boards()


def test_get_cached_industry_boards_hits_cache_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _queued_ok_client(monkeypatch)

    first = get_cached_industry_boards()
    second = get_cached_industry_boards()

    assert first.status == "ok"
    assert first.stale is False
    assert len(first.items) == 2
    assert second.status == "ok"
    assert second.stale is False
    assert [b.code for b in second.items] == ["BK0420", "BK0475"]
    # TTL 内第二次调用不重复请求外网
    assert len(client.calls) == 1


def test_get_cached_industry_boards_refreshes_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _queued_ok_client(monkeypatch)
    client.queue(_make_response(200, _SAMPLE_PAYLOAD))

    get_cached_industry_boards(ttl_seconds=MARKET_BOARD_CACHE_TTL_SECONDS)
    get_cached_industry_boards(ttl_seconds=0)

    assert len(client.calls) == 2


def test_get_cached_industry_boards_returns_stale_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _queued_ok_client(monkeypatch)

    fresh = get_cached_industry_boards()
    assert fresh.status == "ok"
    assert fresh.stale is False

    # TTL 过期后抓取失败：返回上一份缓存并标记 stale
    client.queue(httpx.ConnectError("rate limited"))
    degraded = get_cached_industry_boards(ttl_seconds=0)

    assert degraded.status == "ok"
    assert degraded.stale is True
    assert [b.code for b in degraded.items] == ["BK0420", "BK0475"]
    assert degraded.fetched_at == fresh.fetched_at


def test_get_cached_industry_boards_fetch_failed_without_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    client.queue(httpx.ConnectError("network down"))
    _install_client(monkeypatch, client)

    result = get_cached_industry_boards()

    assert result.status == "fetch_failed"
    assert result.stale is False
    assert result.items == []
    assert result.message is not None


def test_get_cached_industry_boards_fetch_failed_on_bad_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _queued_ok_client(monkeypatch, {"rc": 0, "data": {"diff": "not-a-list"}})

    result = get_cached_industry_boards()

    assert result.status == "fetch_failed"
    assert result.items == []


def test_clear_board_cache_forces_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _queued_ok_client(monkeypatch)
    client.queue(_make_response(200, _SAMPLE_PAYLOAD))

    get_cached_industry_boards()
    clear_board_cache()
    get_cached_industry_boards()

    assert len(client.calls) == 2
