from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.models.watchlist_item import WatchlistItem


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        has_watchlist = session.scalar(select(WatchlistItem.id).limit(1)) is not None
        has_news = session.scalar(select(NewsItem.id).limit(1)) is not None
        has_snapshots = session.scalar(select(PriceSnapshot.id).limit(1)) is not None
        has_topics = session.scalar(select(TopicCluster.id).limit(1)) is not None

        if has_watchlist and has_news and has_snapshots and has_topics:
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
                        volume=18233000,
                        fetched_at=now - timedelta(minutes=2),
                    ),
                    PriceSnapshot(
                        symbol="AAPL",
                        market="us",
                        price=215.32,
                        change_amount=-2.84,
                        change_percent=-1.30,
                        volume=18230000,
                        fetched_at=now - timedelta(minutes=4),
                    ),
                ]
            )

        session.commit()
