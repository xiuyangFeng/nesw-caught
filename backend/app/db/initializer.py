from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text
from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.article_content import ArticleContent
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.models.llm_provider_config import LLMProviderConfig
from app.models.news_analysis_result import NewsAnalysisResult
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.models.watchlist_item import WatchlistItem
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.models.x_account import XAccount
from app.models.x_post import XPost
from app.models.x_post_symbol_mention import XPostSymbolMention
from app.models.x_source_health import XSourceHealth


def ensure_price_snapshot_columns() -> None:
    inspector = inspect(engine)
    if "price_snapshot" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("price_snapshot")}
    required_columns = {
        "open_price": "ALTER TABLE price_snapshot ADD COLUMN open_price FLOAT",
        "previous_close": "ALTER TABLE price_snapshot ADD COLUMN previous_close FLOAT",
        "day_high": "ALTER TABLE price_snapshot ADD COLUMN day_high FLOAT",
        "day_low": "ALTER TABLE price_snapshot ADD COLUMN day_low FLOAT",
        "provider_name": "ALTER TABLE price_snapshot ADD COLUMN provider_name VARCHAR(64)",
        "provider_symbol": "ALTER TABLE price_snapshot ADD COLUMN provider_symbol VARCHAR(32)",
        "quote_status": "ALTER TABLE price_snapshot ADD COLUMN quote_status VARCHAR(32)",
        "status_message": "ALTER TABLE price_snapshot ADD COLUMN status_message VARCHAR(255)",
    }

    with engine.begin() as connection:
        for column_name, statement in required_columns.items():
            if column_name not in existing:
                connection.execute(text(statement))


def ensure_news_item_columns() -> None:
    inspector = inspect(engine)
    if "news_item" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("news_item")}
    required_columns = {
        "signal_status": "ALTER TABLE news_item ADD COLUMN signal_status VARCHAR(32)",
        "signal_error": "ALTER TABLE news_item ADD COLUMN signal_error TEXT",
        "signal_updated_at": "ALTER TABLE news_item ADD COLUMN signal_updated_at DATETIME",
    }

    with engine.begin() as connection:
        for column_name, statement in required_columns.items():
            if column_name not in existing:
                connection.execute(text(statement))


def ensure_topic_cluster_columns() -> None:
    inspector = inspect(engine)
    if "topic_cluster" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("topic_cluster")}
    required_columns = {
        "topic_key": "ALTER TABLE topic_cluster ADD COLUMN topic_key VARCHAR(255)",
        "cluster_version": "ALTER TABLE topic_cluster ADD COLUMN cluster_version INTEGER DEFAULT 1",
        "llm_refined_at": "ALTER TABLE topic_cluster ADD COLUMN llm_refined_at DATETIME",
    }

    with engine.begin() as connection:
        for column_name, statement in required_columns.items():
            if column_name not in existing:
                connection.execute(text(statement))


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_price_snapshot_columns()
    ensure_news_item_columns()
    ensure_topic_cluster_columns()

    with SessionLocal() as session:
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
                        notes="Macro and breaking market headlines",
                    ),
                    XAccount(
                        handle="SawyerMerritt",
                        display_name="Sawyer Merritt",
                        market_focus="us",
                        is_active=True,
                        priority=80,
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
