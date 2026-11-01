"""Seed demo/example data into the News Caught database.

The seed is idempotent: each block only inserts when the corresponding table
is empty, so re-running is always safe.

Standalone usage (uses DATABASE_URL / default settings):

    conda run -n news-caught python scripts/seed_demo_data.py

At application startup the seed runs automatically only when the
``seed_demo_data`` setting (env ``SEED_DEMO_DATA``) is true.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"


def _ensure_backend_on_path() -> None:
    try:
        import app  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(_BACKEND_DIR))


_ensure_backend_on_path()

from datetime import UTC, datetime, timedelta  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.models.article_content import ArticleContent  # noqa: E402
from app.models.news_item import NewsItem  # noqa: E402
from app.models.news_stock_mention import NewsStockMention  # noqa: E402
from app.models.price_snapshot import PriceSnapshot  # noqa: E402
from app.models.topic_cluster import TopicCluster  # noqa: E402
from app.models.topic_news_link import TopicNewsLink  # noqa: E402
from app.models.watchlist_item import WatchlistItem  # noqa: E402


def seed_demo_data(session_factory=None) -> None:
    """Insert demo rows for any of the seedable tables that are still empty."""
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    with session_factory() as session:
        has_watchlist = session.scalar(select(WatchlistItem.id).limit(1)) is not None
        has_news = session.scalar(select(NewsItem.id).limit(1)) is not None
        has_snapshots = session.scalar(select(PriceSnapshot.id).limit(1)) is not None
        has_topics = session.scalar(select(TopicCluster.id).limit(1)) is not None

        if (
            has_watchlist
            and has_news
            and has_snapshots
            and has_topics
        ):
            return

        now = datetime.now(UTC)

        if not has_watchlist:
            session.add_all(
                [
                    WatchlistItem(
                        symbol="0700.HK",
                        market="hk",
                        display_name="Tencent",
                        is_active=True,
                    ),
                    WatchlistItem(
                        symbol="AAPL",
                        market="us",
                        display_name="Apple",
                        is_active=True,
                    ),
                ]
            )

        if not has_news:
            # Clear dangling child tables to prevent foreign key or unique constraint errors on fresh ids
            session.query(ArticleContent).delete()
            session.query(NewsStockMention).delete()
            session.query(NewsItem).delete()
            session.commit()

            news_items = [
                NewsItem(
                    source_name="Reuters",
                    source_url="https://example.com/reuters/tencent",
                    title="Tencent expands enterprise AI product suite",
                    summary="Tencent pushes deeper into enterprise AI workflows and cloud integration.",
                    canonical_url="https://example.com/tencent-ai-suite",
                    url_hash="seed-tencent-ai-suite",
                    market="hk",
                    language="en",
                    sentiment_label="positive",
                    sentiment_score=0.78,
                    published_at=now - timedelta(minutes=25),
                    fetched_at=now - timedelta(minutes=20),
                    ingest_status="ingested",
                ),
                NewsItem(
                    source_name="Bloomberg",
                    source_url="https://example.com/bloomberg/apple-supplier",
                    title="Apple supplier flags softer near-term demand",
                    summary="Supply chain commentary weighs on smartphone sentiment heading into the next cycle.",
                    canonical_url="https://example.com/apple-supplier-demand",
                    url_hash="seed-apple-supplier-demand",
                    market="us",
                    language="en",
                    sentiment_label="negative",
                    sentiment_score=-0.55,
                    published_at=now - timedelta(minutes=18),
                    fetched_at=now - timedelta(minutes=15),
                    ingest_status="ingested",
                ),
            ]
            session.add_all(news_items)
            session.flush()
            session.add_all(
                [
                    ArticleContent(
                        news_id=news_items[0].id,
                        content_text="Tencent highlighted enterprise AI agents and workflow tooling in its latest update.",
                        content_html=None,
                        extract_status="success",
                        extract_error=None,
                        extracted_at=now - timedelta(minutes=19),
                    ),
                    ArticleContent(
                        news_id=news_items[1].id,
                        content_text="Supplier commentary suggests short-term softness in handset component orders.",
                        content_html=None,
                        extract_status="success",
                        extract_error=None,
                        extracted_at=now - timedelta(minutes=14),
                    ),
                    NewsStockMention(
                        news_id=news_items[0].id,
                        symbol="0700.HK",
                        market="hk",
                        mention_type="primary",
                        confidence=0.96,
                    ),
                    NewsStockMention(
                        news_id=news_items[1].id,
                        symbol="AAPL",
                        market="us",
                        mention_type="primary",
                        confidence=0.93,
                    ),
                ]
            )
            session.flush()

        if not has_topics:
            news_by_hash = {
                item.url_hash: item
                for item in session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(["seed-tencent-ai-suite", "seed-apple-supplier-demand"])))
            }
            topics = [
                TopicCluster(
                    topic_title="China internet AI monetization",
                    topic_summary="Platform companies are extending enterprise AI and cloud monetization narratives.",
                    keywords="AI,cloud,enterprise,Tencent",
                    sentiment_score=0.78,
                    importance_score=0.83,
                    last_seen_at=now - timedelta(minutes=20),
                ),
                TopicCluster(
                    topic_title="US smartphone demand softness",
                    topic_summary="Supplier commentary points to softer near-term smartphone and component demand.",
                    keywords="Apple,demand,supply chain,smartphone",
                    sentiment_score=-0.55,
                    importance_score=0.74,
                    last_seen_at=now - timedelta(minutes=15),
                ),
            ]
            session.add_all(topics)
            session.flush()
            if news_by_hash.get("seed-tencent-ai-suite"):
                session.add(
                    TopicNewsLink(
                        topic_cluster_id=topics[0].id,
                        news_id=news_by_hash["seed-tencent-ai-suite"].id,
                    )
                )
            if news_by_hash.get("seed-apple-supplier-demand"):
                session.add(
                    TopicNewsLink(
                        topic_cluster_id=topics[1].id,
                        news_id=news_by_hash["seed-apple-supplier-demand"].id,
                    )
                )

        if not has_snapshots:
            session.add_all(
                [
                    PriceSnapshot(
                        symbol="0700.HK",
                        market="hk",
                        price=332.4,
                        change_amount=10.7,
                        change_percent=3.33,
                        open_price=325.0,
                        previous_close=321.7,
                        day_high=334.8,
                        day_low=323.2,
                        volume=18233000,
                        provider_name="seed",
                        provider_symbol="0700.HK",
                        quote_status="ok",
                        fetched_at=now - timedelta(minutes=2),
                    ),
                    PriceSnapshot(
                        symbol="AAPL",
                        market="us",
                        price=215.32,
                        change_amount=-2.84,
                        change_percent=-1.30,
                        open_price=217.1,
                        previous_close=218.16,
                        day_high=219.4,
                        day_low=214.8,
                        volume=18230000,
                        provider_name="seed",
                        provider_symbol="AAPL",
                        quote_status="ok",
                        fetched_at=now - timedelta(minutes=4),
                    ),
                ]
            )

        session.commit()


if __name__ == "__main__":
    seed_demo_data()
    print("Demo seed data ensured.")
