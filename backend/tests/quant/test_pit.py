"""Point-in-time 截点：晚间公告与财务更正不得泄漏到当时尚不可见的信号。"""

from datetime import UTC, date, datetime

from app.services.quant.contracts import FinancialFact, PitRecord
from app.services.quant.pit import is_available, select_fact_for_display, select_fact_for_signal


def test_evening_announcement_is_not_available_before_next_session() -> None:
    published = datetime(2026, 4, 10, 16, 30, tzinfo=UTC)
    available_next_open = datetime(2026, 4, 13, 1, 30, tzinfo=UTC)  # 周一开盘前
    same_day_cutoff = datetime(2026, 4, 10, 7, 30, tzinfo=UTC)  # 当日 15:30 CST = 07:30 UTC
    record = PitRecord(
        event_at=published,
        source_published_at=published,
        observed_at=published,
        available_at=available_next_open,
    )

    assert is_available(record.available_at, same_day_cutoff) is False
    assert is_available(record.available_at, available_next_open) is True


def test_financial_revision_does_not_leak_into_earlier_signal() -> None:
    original = FinancialFact(
        symbol="600000.SH",
        period_end=date(2025, 12, 31),
        metric_key="net_profit",
        value=1_000.0,
        available_at=datetime(2026, 3, 31, 8, 0, tzinfo=UTC),
        revision_no=1,
        document_id="ann-v1",
    )
    restated = FinancialFact(
        symbol="600000.SH",
        period_end=date(2025, 12, 31),
        metric_key="net_profit",
        value=800.0,
        available_at=datetime(2026, 4, 20, 8, 0, tzinfo=UTC),
        revision_no=2,
        document_id="ann-v2",
    )
    facts = [original, restated]
    before_restatement = datetime(2026, 4, 15, 7, 30, tzinfo=UTC)

    signal_fact = select_fact_for_signal(
        facts, symbol="600000.SH", metric_key="net_profit", signal_cutoff=before_restatement
    )
    display_fact = select_fact_for_display(facts, symbol="600000.SH", metric_key="net_profit")

    assert signal_fact is not None
    assert signal_fact.value == 1_000.0
    assert signal_fact.revision_no == 1
    assert display_fact is not None
    assert display_fact.value == 800.0
    assert display_fact.revision_no == 2
