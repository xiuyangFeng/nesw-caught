"""source_health market backfill and http cache columns

Revision ID: c9d4f0a2b7e1
Revises: ec84dec88ae5
Create Date: 2026-07-06 10:00:00.000000

Formalizes two fixups that previously lived as hand-written SQL inside
``app/db/initializer.py``:

1. Rebuild ``source_health`` with the ``market`` column and the
   ``uq_source_health_source_market`` unique constraint, backfilling the
   market from the most recent ``news_item`` row per source, then from the
   configured source definitions, then ``"unknown"``.
2. Add the ``last_etag`` / ``last_modified`` HTTP cache columns.

Both steps are defensive no-ops when the target schema is already in place
(databases previously repaired by the legacy initializer, or created fresh
via ``Base.metadata.create_all``), so this migration is safe to run against
any existing database in the wild.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'c9d4f0a2b7e1'
down_revision: Union[str, Sequence[str], None] = 'ec84dec88ae5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_source_markets() -> dict[str, str]:
    """Best-effort mapping of configured source name -> market."""
    try:
        from app.services.news_ingestion import load_sources
    except Exception:
        return {}

    source_markets: dict[str, str] = {}
    try:
        for source in load_sources():
            source_markets.setdefault(source.name, source.market)
    except Exception:
        return source_markets
    return source_markets


def _market_for_source(connection, source_name: str, source_markets: dict[str, str], has_news_item: bool) -> str:
    if has_news_item:
        market = connection.execute(
            text(
                """
                SELECT market
                FROM news_item
                WHERE source_name = :source_name AND market IS NOT NULL
                ORDER BY fetched_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"source_name": source_name},
        ).scalar_one_or_none()
        if market:
            return str(market)

    if source_name in source_markets:
        return source_markets[source_name]

    return "unknown"


def _rebuild_source_health_with_market(connection, has_news_item: bool) -> None:
    source_markets = _load_source_markets()

    connection.execute(text("DROP TABLE IF EXISTS source_health_new"))
    connection.execute(
        text(
            """
            CREATE TABLE source_health_new (
                id INTEGER PRIMARY KEY,
                source_name VARCHAR(120) NOT NULL,
                market VARCHAR(16) NOT NULL,
                source_type VARCHAR(16) NOT NULL,
                last_success_at DATETIME,
                last_failure_at DATETIME,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                total_fetches INTEGER NOT NULL DEFAULT 0,
                total_failures INTEGER NOT NULL DEFAULT 0,
                avg_latency_ms FLOAT,
                is_disabled BOOLEAN NOT NULL DEFAULT 0,
                CONSTRAINT uq_source_health_source_market UNIQUE (source_name, market)
            )
            """
        )
    )
    rows = list(connection.execute(text("SELECT * FROM source_health")).mappings())
    for row in rows:
        market = row.get("market") or _market_for_source(
            connection, str(row["source_name"]), source_markets, has_news_item
        )
        connection.execute(
            text(
                """
                INSERT INTO source_health_new (
                    id, source_name, market, source_type,
                    last_success_at, last_failure_at,
                    consecutive_failures, total_fetches, total_failures,
                    avg_latency_ms, is_disabled
                ) VALUES (
                    :id, :source_name, :market, :source_type,
                    :last_success_at, :last_failure_at,
                    :consecutive_failures, :total_fetches, :total_failures,
                    :avg_latency_ms, :is_disabled
                )
                """
            ),
            {
                "id": row["id"],
                "source_name": row["source_name"],
                "market": market,
                "source_type": row["source_type"],
                "last_success_at": row["last_success_at"],
                "last_failure_at": row["last_failure_at"],
                "consecutive_failures": row["consecutive_failures"],
                "total_fetches": row["total_fetches"],
                "total_failures": row["total_failures"],
                "avg_latency_ms": row["avg_latency_ms"],
                "is_disabled": row["is_disabled"],
            },
        )
    connection.execute(text("DROP TABLE source_health"))
    connection.execute(text("ALTER TABLE source_health_new RENAME TO source_health"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_health_source_name ON source_health (source_name)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_source_health_market ON source_health (market)"))


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    if "source_health" not in tables:
        # Fresh databases are created via Base.metadata.create_all and stamped
        # at head; if the table is missing there is nothing to repair.
        return

    columns = {column["name"] for column in inspector.get_columns("source_health")}
    if "market" not in columns:
        _rebuild_source_health_with_market(connection, "news_item" in tables)
        columns = {column["name"] for column in sa.inspect(connection).get_columns("source_health")}

    if "last_etag" not in columns:
        connection.execute(text("ALTER TABLE source_health ADD COLUMN last_etag VARCHAR(256) DEFAULT NULL"))
    if "last_modified" not in columns:
        connection.execute(text("ALTER TABLE source_health ADD COLUMN last_modified VARCHAR(128) DEFAULT NULL"))


def downgrade() -> None:
    """Repair migration; there is no meaningful schema state to restore."""
    pass
