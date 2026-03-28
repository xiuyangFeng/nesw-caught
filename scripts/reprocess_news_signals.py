"""Reprocess news signal classification for existing news items.

Usage:
    conda run -n news-caught python scripts/reprocess_news_signals.py [options]

Options:
    --limit N     Process at most N news items (default: all pending)
    --all         Reprocess ALL news items, including already processed ones
    --dry-run     Only count and print, do not execute
    --batch-size  Number of items per batch (default: 50)
"""

from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.services.news_signal_pipeline import NewsSignalPipelineService
from sqlalchemy import func, select


def count_pending(session, *, include_all: bool) -> int:
    if include_all:
        return session.scalar(select(func.count(NewsItem.id))) or 0
    return (
        session.scalar(
            select(func.count(NewsItem.id)).where(NewsItem.signal_status.is_(None))
        )
        or 0
    )


def fetch_ids(session, *, include_all: bool, limit: int) -> list[int]:
    if include_all:
        stmt = select(NewsItem.id).order_by(NewsItem.id.asc())
    else:
        stmt = (
            select(NewsItem.id)
            .where(NewsItem.signal_status.is_(None))
            .order_by(NewsItem.id.asc())
        )
    if limit > 0:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess news signal classification")
    parser.add_argument(
        "--limit", type=int, default=0, help="Max items to process (0 = all)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Reprocess all items, not just pending"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only count, do not process"
    )
    parser.add_argument("--batch-size", type=int, default=50, help="Items per batch")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        total = count_pending(session, include_all=args.all)
        mode = "all" if args.all else "pending"
        print(
            f"[reprocess] mode={mode}  total_count={total}  batch_size={args.batch_size}"
        )

        if args.dry_run:
            print("[reprocess] dry-run: stopping here.")
            return

        ids = fetch_ids(session, include_all=args.all, limit=args.limit)
        if not ids:
            print("[reprocess] nothing to process.")
            return

        batch_size = args.batch_size
        processed = 0
        start = time.time()

        for offset in range(0, len(ids), batch_size):
            batch = ids[offset : offset + batch_size]
            pipeline = NewsSignalPipelineService(session)
            result = pipeline.process_news_ids(batch)
            session.commit()
            processed += result.processed_count
            elapsed = time.time() - start
            print(
                f"[reprocess] batch offset={offset}  "
                f"processed={result.processed_count}  "
                f"topics_touched={len(result.touched_topic_ids)}  "
                f"total={processed}/{len(ids)}  "
                f"elapsed={elapsed:.1f}s"
            )

        elapsed = time.time() - start
        print(f"[reprocess] done  total_processed={processed}  elapsed={elapsed:.1f}s")
    finally:
        session.close()


if __name__ == "__main__":
    main()
