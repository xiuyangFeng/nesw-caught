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

from datetime import datetime, timedelta, timezone  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.models.article_content import ArticleContent  # noqa: E402
from app.models.news_item import NewsItem  # noqa: E402
from app.models.news_stock_mention import NewsStockMention  # noqa: E402
from app.models.price_snapshot import PriceSnapshot  # noqa: E402
from app.models.topic_cluster import TopicCluster  # noqa: E402
from app.models.topic_news_link import TopicNewsLink  # noqa: E402
from app.models.watchlist_item import WatchlistItem  # noqa: E402
from app.models.x_account import XAccount  # noqa: E402
from app.models.x_post import XPost  # noqa: E402
from app.models.x_post_symbol_mention import XPostSymbolMention  # noqa: E402
from app.models.x_source_health import XSourceHealth  # noqa: E402


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
        has_x_accounts = session.scalar(select(XAccount.id).limit(1)) is not None
        has_x_posts = session.scalar(select(XPost.id).limit(1)) is not None
        has_x_health = session.scalar(select(XSourceHealth.id).limit(1)) is not None

        if has_watchlist and has_news and has_snapshots and has_topics and has_x_accounts and has_x_posts and has_x_health:
            return

        now = datetime.now(timezone.utc)

        if not has_watchlist:
            session.add_all(
                [
                    WatchlistItem(
                        symbol="0700.HK",
                        market="hk",
                        display_name="Tencent",
                        is_active=True,
                        alert_threshold=3.0,
                        alert_mode="fixed",
                    ),
                    WatchlistItem(
                        symbol="AAPL",
                        market="us",
                        display_name="Apple",
                        is_active=True,
                        alert_threshold=2.0,
                        alert_mode="fixed",
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

        if not has_x_accounts:
            session.add_all(
                [
                    XAccount(
                        handle="DeItaone",
                        display_name="Delta One",
                        market_focus="us",
                        is_active=True,
                        priority=100,
                        tier="core",
                        source="manual",
                        notes="Macro and breaking market headlines",
                    ),
                    XAccount(
                        handle="SawyerMerritt",
                        display_name="Sawyer Merritt",
                        market_focus="us",
                        is_active=True,
                        priority=80,
                        tier="watch",
                        source="manual",
                        notes="Tech and EV market chatter",
                    ),
                ]
            )
            session.flush()

        if not has_x_posts:
            account_by_handle = {
                item.handle: item
                for item in session.scalars(select(XAccount).where(XAccount.handle.in_(["DeItaone", "SawyerMerritt"])))
            }
            x_posts: list[XPost] = []
            if account_by_handle.get("DeItaone"):
                x_posts.append(
                    XPost(
                        account_id=account_by_handle["DeItaone"].id,
                        external_post_id="190001",
                        canonical_url="https://x.com/DeItaone/status/190001",
                        content_text="NVIDIA suppliers remain in focus as AI infrastructure demand signals stay firm into the next quarter.",
                        market="us",
                        sentiment_label="positive",
                        relevance_score=0.92,
                        posted_at=now - timedelta(minutes=13),
                        captured_at=now - timedelta(minutes=5),
                        raw_payload_json='{"account_handle":"DeItaone"}',
                        dedupe_hash="seed-x-post-deltaone-190001",
                    )
                )
            if account_by_handle.get("SawyerMerritt"):
                x_posts.append(
                    XPost(
                        account_id=account_by_handle["SawyerMerritt"].id,
                        external_post_id="190002",
                        canonical_url="https://x.com/SawyerMerritt/status/190002",
                        content_text="Tesla supply chain comments are weighing on near-term EV sentiment after softer delivery expectations.",
                        market="us",
                        sentiment_label="negative",
                        relevance_score=0.84,
                        posted_at=now - timedelta(minutes=18),
                        captured_at=now - timedelta(minutes=6),
                        raw_payload_json='{"account_handle":"SawyerMerritt"}',
                        dedupe_hash="seed-x-post-sawyermerritt-190002",
                    )
                )
            session.add_all(x_posts)
            session.flush()
            mentions: list[XPostSymbolMention] = []
            for item in x_posts:
                if item.external_post_id == "190001":
                    mentions.append(XPostSymbolMention(x_post_id=item.id, symbol="NVDA", market="us", confidence=0.8))
                if item.external_post_id == "190002":
                    mentions.append(XPostSymbolMention(x_post_id=item.id, symbol="TSLA", market="us", confidence=0.8))
            session.add_all(mentions)

        if not has_x_health:
            session.add(
                XSourceHealth(
                    provider_name="twitterapi.io",
                    total_fetches=0,
                    total_failures=0,
                    consecutive_failures=0,
                    avg_latency_ms=None,
                    last_error=None,
                )
            )

        session.commit()


if __name__ == "__main__":
    seed_demo_data()
    print("Demo seed data ensured.")
