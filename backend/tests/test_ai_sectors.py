"""关注板块：自选股板块并集 + 用户增删；AI 推断个股板块。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.sector import FocusSectorOverride, StockSector
from app.models.watchlist_item import WatchlistItem
from app.services.ai.sectors import (
    SectorInferenceService,
    add_focus_sector,
    list_focus_sectors,
    remove_focus_sector,
)
from app.services.llm_providers import LLMProviderError


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
            session.execute(delete(StockSector))
            session.execute(delete(FocusSectorOverride))
            session.execute(delete(WatchlistItem))
            session.commit()

    wipe()
    yield
    wipe()


def _watch(session, symbol: str, name: str, *, position: float | None = None, active: bool = True) -> None:
    session.add(
        WatchlistItem(symbol=symbol, market="cn", display_name=name, is_active=active, position_size=position)
    )


def test_focus_sectors_union_of_watchlist_sectors_plus_user_overrides() -> None:
    with SessionLocal() as session:
        _watch(session, "688256.SH", "寒武纪", position=100)
        _watch(session, "002384.SZ", "东山精密")
        _watch(session, "600000.SH", "浦发银行", active=False)
        session.add_all(
            [
                StockSector(symbol="688256.SH", sector="半导体", source="ai"),
                StockSector(symbol="688256.SH", sector="AI芯片", source="ai"),
                StockSector(symbol="002384.SZ", sector="消费电子", source="ai"),
                StockSector(symbol="002384.SZ", sector="半导体", source="ai"),
                StockSector(symbol="600000.SH", sector="银行", source="ai"),  # 已停用的自选不算
            ]
        )
        session.commit()

        names = [sector.name for sector in list_focus_sectors(session)]
        assert names == ["半导体", "AI芯片", "消费电子"]
        chip = next(sector for sector in list_focus_sectors(session) if sector.name == "半导体")
        assert chip.symbols == ["688256.SH", "002384.SZ"]
        assert chip.source == "ai"

        remove_focus_sector(session, "消费电子")
        add_focus_sector(session, "光模块")
        session.commit()
        sectors = list_focus_sectors(session)
        assert [sector.name for sector in sectors] == ["半导体", "AI芯片", "光模块"]
        assert sectors[-1].source == "user" and sectors[-1].symbols == []

        # 删除后再添加 = 恢复
        add_focus_sector(session, "消费电子")
        session.commit()
        assert "消费电子" in [sector.name for sector in list_focus_sectors(session)]


def test_add_focus_sector_rejects_blank_names() -> None:
    with SessionLocal() as session, pytest.raises(ValueError):
        add_focus_sector(session, "   ")


def test_infer_missing_sectors_for_watchlist_stocks() -> None:
    with SessionLocal() as session:
        _watch(session, "688256.SH", "寒武纪", position=100)
        _watch(session, "002384.SZ", "东山精密")
        session.add(StockSector(symbol="002384.SZ", sector="消费电子", source="ai"))
        session.commit()

    provider = FakeProvider([{"sectors": ["AI芯片", "半导体", "AI芯片", "", "x" * 80]}])
    with SessionLocal() as session:
        inferred = SectorInferenceService(session, provider).infer_missing(limit=5)
        session.commit()
        assert inferred == 1
        rows = session.scalars(select(StockSector.sector).where(StockSector.symbol == "688256.SH")).all()
        assert sorted(rows) == ["AI芯片", "半导体"]
    assert len(provider.calls) == 1
    assert provider.calls[0]["operation_type"] == "sector_infer"
    assert "寒武纪" in provider.calls[0]["messages"][1]["content"]


def test_infer_missing_sectors_skips_on_llm_failure() -> None:
    with SessionLocal() as session:
        _watch(session, "688256.SH", "寒武纪")
        session.commit()

    provider = FakeProvider([LLMProviderError("boom")])
    with SessionLocal() as session:
        assert SectorInferenceService(session, provider).infer_missing(limit=5) == 0
        assert session.scalars(select(StockSector)).all() == []


def test_infer_missing_reports_failures_and_honours_exclude() -> None:
    with SessionLocal() as session:
        _watch(session, "688256.SH", "寒武纪")
        _watch(session, "600519.SH", "贵州茅台")
        session.commit()

    provider = FakeProvider([{"sectors": ["白酒"]}])
    with SessionLocal() as session:
        service = SectorInferenceService(session, provider)
        assert service.infer_missing(limit=1, exclude={"688256.SH"}) == 1
        assert service.failed_symbols == []
        assert "贵州茅台" in provider.calls[0]["messages"][1]["content"]

    provider = FakeProvider([{"sectors": []}])
    with SessionLocal() as session:
        service = SectorInferenceService(session, provider)
        assert service.infer_missing(limit=1) == 0
        assert service.failed_symbols == ["688256.SH"]
