"""真实选票流水线：无数据降级、trend 资格判定、event mention 观察态、涨跌停闸门、哈希可复现。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.services.quant.contracts import CandidateState, RunStatus, RunVersions, Sleeve
from app.services.quant.recommendation.market_pipeline import run_market_pipeline
from app.services.quant.trading_rules import RULE_VERSION


def _cleanup() -> None:
    with MarketSessionLocal() as market_session:
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.commit()
    with SessionLocal() as session:
        # 只清理本文件写入的新闻（url_hash 前缀区分），不动 demo seed 数据。
        session.query(NewsItem).filter(NewsItem.url_hash.like("mp-test-%")).delete(synchronize_session=False)
        session.commit()


def _versions(source_cutoff: datetime | None = None) -> RunVersions:
    return RunVersions(
        dataset_version="test-eastmoney-daily",
        factor_version="rule-v1",
        rule_version=RULE_VERSION,
        code_commit="test",
        config_snapshot={},
        source_cutoff=source_cutoff or datetime.now(UTC),
    )


def _seed_bars(
    market_session,
    symbol: str,
    *,
    last_date: date,
    days: int = 130,
    amount: float = 2e8,
    base_close: float = 10.0,
    last_open: float | None = None,
) -> None:
    last_row = None
    for i in range(days):
        trade_date = last_date - timedelta(days=days - 1 - i)
        row = DailyBar(
            symbol=symbol,
            trade_date=trade_date,
            open=base_close,
            high=base_close,
            low=base_close,
            close=base_close,
            volume=1000,
            amount=amount,
        )
        market_session.add(row)
        if trade_date == last_date:
            last_row = row
    if last_open is not None and last_row is not None:
        last_row.open = last_open


def _seed_rule_mention(session, *, symbol: str, url_hash: str, published_at: datetime, title: str = "测试新闻") -> None:
    news = NewsItem(
        source_name="test",
        source_url=f"https://example.com/{url_hash}",
        title=title,
        canonical_url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        market="cn",
        published_at=published_at,
        fetched_at=published_at,
        ingest_status="ingested",
    )
    session.add(news)
    session.flush()
    session.add(
        NewsStockMention(news_id=news.id, symbol=symbol, market="cn", mention_type="rule", confidence=0.9)
    )


def test_no_market_data_returns_degraded() -> None:
    _cleanup()
    result = run_market_pipeline(versions=_versions())
    assert result.status is RunStatus.DEGRADED
    assert result.empty_reason == "no_market_data"
    assert result.items == []
    assert result.qualified == []


def test_trend_candidate_generation_and_qualify() -> None:
    _cleanup()
    today = date.today()
    symbol = "000001.SZ"
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()
        market_session.add(FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=8e7, main_net_pct=0.1))
        market_session.commit()

    result = run_market_pipeline(versions=_versions())
    assert result.status is RunStatus.OK
    trend_items = [item for item in result.items if item.sleeve is Sleeve.TREND_FLOW]
    assert len(trend_items) == 1
    item = trend_items[0]
    assert item.symbol == symbol
    assert item.state is CandidateState.QUALIFIED
    assert item.reason_code == "trend_qualified"
    assert item.rank == 1
    assert "ret_20d" in item.factor_breakdown
    assert result.qualified and result.qualified[0].symbol == symbol


def test_trend_candidate_below_threshold_stays_watch() -> None:
    _cleanup()
    today = date.today()
    symbol = "000002.SZ"
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()
        # 净流出：不满足 score_trend 的 qualify 条件。
        market_session.add(FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=-1e7, main_net_pct=-0.1))
        market_session.commit()

    result = run_market_pipeline(versions=_versions())
    trend_items = [item for item in result.items if item.sleeve is Sleeve.TREND_FLOW]
    assert len(trend_items) == 1
    assert trend_items[0].state is CandidateState.WATCH
    assert trend_items[0].reason_code == "trend_liquidity_or_flow_short"
    assert trend_items[0] not in result.qualified


def test_event_mention_produces_watch_candidate() -> None:
    _cleanup()
    today = date.today()
    symbol = "000003.SZ"
    now = datetime.now(UTC)
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()
    with SessionLocal() as session:
        _seed_rule_mention(session, symbol=symbol, url_hash="mp-test-event-1", published_at=now - timedelta(days=1))
        session.commit()

    result = run_market_pipeline(versions=_versions(source_cutoff=now))
    event_items = [item for item in result.items if item.sleeve is Sleeve.EVENT_CATALYST]
    assert len(event_items) == 1
    item = event_items[0]
    assert item.symbol == symbol
    assert item.state is CandidateState.WATCH
    assert item.reason_code == "event_below_threshold_or_weak_evidence"
    assert item.factor_breakdown.get("news_novelty", 0) > 0
    assert item not in result.qualified


def test_no_mention_means_no_event_candidate() -> None:
    _cleanup()
    today = date.today()
    symbol = "000004.SZ"
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()

    result = run_market_pipeline(versions=_versions())
    event_items = [item for item in result.items if item.sleeve is Sleeve.EVENT_CATALYST]
    assert event_items == []


def test_limit_up_open_downgrades_qualified_to_watch() -> None:
    _cleanup()
    today = date.today()
    symbol = "000005.SZ"
    with MarketSessionLocal() as market_session:
        # 前一日收盘 10.0，当日开盘 11.05（>=10% 涨停价 11.0），触发涨停开盘不可成交。
        _seed_bars(market_session, symbol, last_date=today, last_open=11.05)
        market_session.commit()
        market_session.add(FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=8e7, main_net_pct=0.1))
        market_session.commit()

    result = run_market_pipeline(versions=_versions())
    trend_items = [item for item in result.items if item.sleeve is Sleeve.TREND_FLOW]
    assert len(trend_items) == 1
    item = trend_items[0]
    assert item.state is CandidateState.WATCH
    assert item.reason_code == "limit_up_open_unfillable"
    assert item.symbol not in [q.symbol for q in result.qualified]


def test_hash_reproducible_for_same_snapshot() -> None:
    _cleanup()
    today = date.today()
    symbol = "000006.SZ"
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()
        market_session.add(FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=8e7, main_net_pct=0.1))
        market_session.commit()

    versions = _versions()
    first = run_market_pipeline(versions=versions)
    second = run_market_pipeline(versions=versions)
    assert first.result_hash == second.result_hash
    assert first.result_hash != ""


def test_fundamental_sleeve_produces_no_fabricated_candidates() -> None:
    _cleanup()
    today = date.today()
    symbol = "000007.SZ"
    with MarketSessionLocal() as market_session:
        _seed_bars(market_session, symbol, last_date=today)
        market_session.commit()

    result = run_market_pipeline(versions=_versions())
    fundamental_items = [item for item in result.items if item.sleeve is Sleeve.FUNDAMENTAL_REVALUE]
    assert fundamental_items == []
    stage = next(s for s in result.stages if s.stage == "sleeve_fundamental_revalue")
    assert stage.detail["scored"] == 0
    assert stage.detail["gap_symbols"] >= 1
