"""market_index_config 表与 MarketOverviewRepository 的 CRUD 测试。

对应设计文档四节（新表 market_index_config）与计划任务 B1：
- 字段：id/symbol/market/display_name/kind/sort_order/enabled/created_at/updated_at；
- 约束：(symbol, market) 唯一；(market, enabled, sort_order) 复合索引；
- repository：list_all / list_enabled / get / create / update / delete，
  排序按 (market, sort_order)；update 不提供修改 symbol/market 的入口。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.market_index_config import MarketIndexConfig
from app.repositories.market_overview_repository import MarketOverviewRepository


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


def _create(
    repo: MarketOverviewRepository,
    *,
    symbol: str = "^GSPC",
    market: str = "us",
    display_name: str = "标普500",
    **kwargs,
) -> MarketIndexConfig:
    return repo.create(
        symbol=symbol,
        market=market,
        display_name=display_name,
        **kwargs,
    )


def test_create_applies_defaults_and_timestamps(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        item = _create(repo, symbol="^VIX", display_name="恐慌指数")

        assert item.id is not None
        assert item.symbol == "^VIX"
        assert item.market == "us"
        # kind 缺省为 index、sort_order 缺省 0、enabled 缺省 True。
        assert item.kind == "index"
        assert item.sort_order == 0
        assert item.enabled is True
        assert item.created_at is not None
        assert item.updated_at is not None


def test_duplicate_symbol_market_pair_raises_integrity_error(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        _create(repo, symbol="^GSPC", market="us")

        with pytest.raises(IntegrityError):
            _create(repo, symbol="^GSPC", market="us", display_name="重复条目")
        session.rollback()

        # 同 symbol 不同 market 允许共存。
        other = _create(repo, symbol="^GSPC", market="eu", display_name="另一市场")
        assert other.id is not None


def test_list_all_sorted_by_market_then_sort_order(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        _create(repo, symbol="^IXIC", market="us", display_name="纳斯达克", sort_order=2)
        _create(repo, symbol="000300.SS", market="cn", display_name="沪深300", sort_order=1)
        _create(repo, symbol="^GSPC", market="us", display_name="标普500", sort_order=1)
        _create(repo, symbol="000001.SS", market="cn", display_name="上证指数", sort_order=2)

        items = repo.list_all()

        assert [(item.market, item.symbol) for item in items] == [
            ("cn", "000300.SS"),
            ("cn", "000001.SS"),
            ("us", "^GSPC"),
            ("us", "^IXIC"),
        ]


def test_list_enabled_filters_disabled_and_keeps_sort_order(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        _create(repo, symbol="^GSPC", market="us", display_name="标普500", sort_order=1)
        _create(repo, symbol="^VIX", market="us", display_name="恐慌指数", sort_order=2, enabled=False)
        _create(repo, symbol="^KS11", market="kr", display_name="韩国KOSPI", sort_order=1)

        items = repo.list_enabled()

        assert [(item.market, item.symbol) for item in items] == [
            ("kr", "^KS11"),
            ("us", "^GSPC"),
        ]
        assert all(item.enabled for item in items)


def test_get_returns_row_by_id(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        created = _create(repo)

        assert repo.get(created.id).symbol == "^GSPC"
        assert repo.get(999999) is None


def test_update_only_touches_mutable_fields(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        created = _create(repo, symbol="XLK", display_name="科技ETF", kind="etf")

        updated = repo.update(
            created.id,
            {"display_name": "科技精选ETF", "sort_order": 5, "enabled": False, "kind": "index"},
        )

        assert updated is not None
        assert updated.display_name == "科技精选ETF"
        assert updated.sort_order == 5
        assert updated.enabled is False
        assert updated.kind == "index"
        # symbol 与 market 不在 update 的可写字段内，必须保持原值。
        assert updated.symbol == "XLK"
        assert updated.market == "us"
        assert updated.updated_at >= created.updated_at


def test_update_ignores_unknown_keys_and_missing_id(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        created = _create(repo)

        # 即使调用方误传 symbol/market，repository 也不得写入（接口层契约：
        # symbol/market 不允许改，改了应当删除+新增）。
        updated = repo.update(created.id, {"symbol": "^IXIC", "market": "cn", "display_name": "改名"})
        assert updated.symbol == "^GSPC"
        assert updated.market == "us"
        assert updated.display_name == "改名"

        assert repo.update(999999, {"display_name": "不存在"}) is None


def test_delete_removes_row(session_factory) -> None:
    with session_factory() as session:
        repo = MarketOverviewRepository(session)
        created = _create(repo)

        assert repo.delete(created.id) is True
        assert repo.get(created.id) is None
        assert repo.delete(created.id) is False
        assert session.scalar(select(MarketIndexConfig).where(MarketIndexConfig.id == created.id)) is None
