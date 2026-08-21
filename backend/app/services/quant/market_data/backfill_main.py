"""CLI: PYTHONPATH=backend python -m app.services.quant.market_data.backfill_main

可用环境变量:
- QUANT_BACKFILL_LIMIT  回填标的数上限,默认 100(全量约 6141,请求量 = 2 × 标的数)
- QUANT_BACKFILL_SLEEP  每只标的之间的间隔秒,默认 0.5(东财限流实测存在,勿设 0)
- QUANT_BACKFILL_DAYS   回填天数,默认 1095(约 3 年)
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.db.market_initializer import initialize_market_database
from app.services.a_share_search_service import get_all_a_shares
from app.services.quant.market_data.backfill import backfill_symbols


def _backfill_financials(symbols: list[str], *, sleep_seconds: float) -> dict:
    """对给定标的抓东财主要财务指标并幂等落库；单标的失败不阻断整批。"""
    import time

    from app.db.market_session import MarketSessionLocal
    from app.services.quant.market_data.backfill import upsert_financial_facts
    from app.services.quant.market_data.eastmoney_financials import fetch_financials

    count = 0
    failures = 0
    for symbol in symbols:
        try:
            rows = fetch_financials(symbol)
            with MarketSessionLocal() as session:
                count += upsert_financial_facts(session, rows)
                session.commit()
        except Exception:
            failures += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return {"financial_facts": count, "failures": failures, "symbols": len(symbols)}


def main() -> None:
    initialize_market_database()
    settings = get_settings()
    limit = int(os.environ.get("QUANT_BACKFILL_LIMIT", "100"))
    sleep_seconds = float(os.environ.get("QUANT_BACKFILL_SLEEP", "0.5"))
    days = int(os.environ.get("QUANT_BACKFILL_DAYS", "1095"))
    end = date.today()
    start = end - timedelta(days=days)
    symbols = [row["symbol"] for row in get_all_a_shares()[:limit]]
    checkpoint = Path(settings.market_database_url.replace("sqlite:///", "")).with_name(
        "quant_backfill_checkpoint.json"
    )
    summary = backfill_symbols(
        symbols, start=start, end=end, checkpoint_path=checkpoint, sleep_seconds=sleep_seconds
    )
    print(summary)
    # 可选：同时抓财务指标（东财 f10 接口，独立限流预算）。
    if os.environ.get("QUANT_BACKFILL_FINANCIALS", "0") == "1":
        financial_summary = _backfill_financials(symbols, sleep_seconds=sleep_seconds)
        print(financial_summary)


if __name__ == "__main__":
    main()
