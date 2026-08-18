"""CLI: PYTHONPATH=backend python -m app.services.quant.market_data.backfill_main"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.db.market_initializer import initialize_market_database
from app.services.a_share_search_service import get_all_a_shares
from app.services.quant.market_data.backfill import backfill_symbols


def main() -> None:
    initialize_market_database()
    settings = get_settings()
    end = date.today()
    start = end - timedelta(days=365 * 3)
    symbols = [row["symbol"] for row in get_all_a_shares()[:100]]
    checkpoint = Path(settings.market_database_url.replace("sqlite:///", "")).with_name(
        "quant_backfill_checkpoint.json"
    )
    summary = backfill_symbols(symbols, start=start, end=end, checkpoint_path=checkpoint)
    print(summary)


if __name__ == "__main__":
    main()
