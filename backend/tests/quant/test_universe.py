"""三层股票池：历史 U2 必须按当日证券状态重建，不能拿今天的名单回放过去。"""

from datetime import date

from app.services.quant.contracts import Board, SecurityMasterRow
from app.services.quant.universe import build_u2, securities_as_of


def _row(**overrides: object) -> SecurityMasterRow:
    base = dict(
        symbol="600000.SH",
        name="浦发银行",
        exchange="SH",
        board=Board.MAIN,
        list_date=date(1999, 11, 10),
        delist_date=None,
        status="listed",
        industry_code="801780",
        effective_from=date(1999, 11, 10),
        effective_to=None,
        median_amount_20d=5e8,
    )
    base.update(overrides)
    return SecurityMasterRow(**base)  # type: ignore[arg-type]


def test_u0_as_of_keeps_historical_name_and_excludes_future_rename() -> None:
    master = [
        _row(name="旧名", effective_from=date(2020, 1, 1), effective_to=date(2024, 12, 31)),
        _row(name="新名", effective_from=date(2025, 1, 1), effective_to=None),
    ]
    past = securities_as_of(master, date(2024, 6, 1))
    today = securities_as_of(master, date(2026, 4, 10))
    assert [row.name for row in past] == ["旧名"]
    assert [row.name for row in today] == ["新名"]


def test_u2_excludes_halted_ipo_and_illiquid_names() -> None:
    as_of = date(2026, 4, 10)
    master = [
        _row(symbol="600000.SH"),
        _row(symbol="600001.SH", status="halted"),
        _row(symbol="688001.SH", board=Board.STAR, list_date=date(2026, 3, 1), median_amount_20d=8e8),
        _row(symbol="301001.SZ", board=Board.CHINEXT, median_amount_20d=1e7),
        _row(
            symbol="EXDEAD.SH",
            status="delisted",
            delist_date=date(2023, 6, 1),
            effective_to=date(2023, 6, 1),
        ),
    ]
    symbols = set(build_u2(master, as_of))
    assert symbols == {"600000.SH"}


def test_historical_u2_includes_later_delisted_name() -> None:
    master = [
        _row(
            symbol="EXDEAD.SH",
            status="listed",
            delist_date=date(2023, 6, 1),
            effective_from=date(2010, 1, 1),
            effective_to=date(2023, 6, 1),
            median_amount_20d=3e8,
        )
    ]
    past = set(build_u2(master, date(2022, 6, 1)))
    today = set(build_u2(master, date(2026, 4, 10)))
    assert past == {"EXDEAD.SH"}
    assert today == set()
