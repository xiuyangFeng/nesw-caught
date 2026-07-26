from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session, load_only

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_cursor import decode_cursor, encode_cursor

# 列表/摘要场景只需要 NewsItemSummary 用到的列。默认全列 hydrate 会把
# signal_error(Text)、source_url、url_hash 等列表页从不读的字段一起拉回来，
# limit=200 时相当于每请求多搬运 200 行的无用列。
NEWS_SUMMARY_COLUMNS = (
    NewsItem.id,
    NewsItem.title,
    NewsItem.summary,
    NewsItem.source_name,
    NewsItem.canonical_url,
    NewsItem.market,
    NewsItem.sentiment_label,
    NewsItem.published_at,
    NewsItem.fetched_at,
    NewsItem.effective_at,
    NewsItem.ai_takeaway,
)


def news_summary_load_option():
    """只加载 NewsItemSummary 需要的列(其余列保持 deferred，访问时才回表)。"""
    return load_only(*NEWS_SUMMARY_COLUMNS)


# “news_fts 虚拟表是否可用”是进程级事实(建表由启动迁移完成),一旦探明不可用就
# 不必每次搜索再触发一次异常往返。None=未知,True/False=已探明。
_fts_available: bool | None = None


def reset_fts_availability_cache() -> None:
    """测试/运维用:清空 FTS 可用性的进程内缓存。"""
    global _fts_available
    _fts_available = None


@dataclass(frozen=True)
class NewsDetailBundle:
    item: NewsItem
    article: ArticleContent | None
    mentions: list[NewsStockMention]
    topic: TopicCluster | None


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_recent(
        self,
        *,
        limit: int = 50,
        market: str | None = None,
        source_name: str | None = None,
        sentiment_label: str | None = None,
        query: str | None = None,
    ) -> list[NewsItem]:
        items, _ = self.list_recent_page(
            limit=limit,
            market=market,
            source_name=source_name,
            sentiment_label=sentiment_label,
            query=query,
        )
        return items

    def list_recent_page(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        market: str | None = None,
        source_name: str | None = None,
        sentiment_label: str | None = None,
        query: str | None = None,
    ) -> tuple[list[NewsItem], str | None]:
        global _fts_available

        # 列表页只消费 NewsItemSummary 字段,其余列保持 deferred(见 NEWS_SUMMARY_COLUMNS)。
        base_stmt = select(NewsItem).options(news_summary_load_option())

        if market:
            base_stmt = base_stmt.where(NewsItem.market == market)

        if source_name:
            base_stmt = base_stmt.where(NewsItem.source_name == source_name)

        if sentiment_label:
            base_stmt = base_stmt.where(NewsItem.sentiment_label == sentiment_label)

        def _finalize(stmt):
            if cursor:
                cursor_effective_at, cursor_id = decode_cursor(cursor)
                if cursor_effective_at is None:
                    stmt = stmt.where(NewsItem.id < cursor_id)
                else:
                    stmt = stmt.where(
                        or_(
                            NewsItem.effective_at < cursor_effective_at,
                            and_(
                                NewsItem.effective_at == cursor_effective_at,
                                NewsItem.id < cursor_id,
                            ),
                        )
                    )
            # Sort by effective_at (= published_at ?? fetched_at) so Chinese feeds
            # without publish time no longer sink. Index: ix_news_effective_id /
            # ix_news_market_effective_id.
            return stmt.order_by(
                NewsItem.effective_at.desc(),
                NewsItem.id.desc(),
            ).limit(limit + 1)

        def _like_stmt():
            keyword = f"%{query.strip().lower()}%"
            return _finalize(
                base_stmt.where(
                    or_(
                        func.lower(NewsItem.title).like(keyword),
                        func.lower(func.coalesce(NewsItem.summary, "")).like(keyword),
                    )
                )
            )

        safe_query = " ".join([w for w in query.strip().split() if w]) if query else ""

        rows: list[NewsItem] | None = None
        if query and safe_query and _fts_available is not False:
            # 旧实现固定先跑一次 LIMIT 1 的 MATCH 探针再跑正查,每次搜索白付一次往返。
            # 现在直接跑 FTS 正查:命中即 1 次往返;只有“查不到”才需要区分
            # “FTS 无命中(该回退 LIKE)”与“游标已翻到底(该返回空页)”。
            fts_subquery = text("SELECT rowid FROM news_fts WHERE news_fts MATCH :q").bindparams(
                q=safe_query
            )
            try:
                rows = list(
                    self.session.scalars(_finalize(base_stmt.where(NewsItem.id.in_(fts_subquery))))
                )
                _fts_available = True
            except Exception:
                _fts_available = False
                rows = None
            if rows is not None and not rows:
                # 无游标时空结果只可能是 FTS 没命中(CJK 分词 miss 等),直接回退 LIKE;
                # 带游标时才需要补一次探针来区分“翻到底”。
                fallback_to_like = True
                if cursor:
                    probe = text(
                        "SELECT rowid FROM news_fts WHERE news_fts MATCH :q LIMIT 1"
                    ).bindparams(q=safe_query)
                    try:
                        fallback_to_like = self.session.execute(probe).first() is None
                    except Exception:
                        _fts_available = False
                        fallback_to_like = True
                if fallback_to_like:
                    rows = None

        if rows is None:
            rows = list(self.session.scalars(_like_stmt() if query and safe_query else _finalize(base_stmt)))

        has_more = len(rows) > limit
        items = rows[:limit]
        if not has_more or not items:
            return items, None

        last = items[-1]
        return items, encode_cursor(effective_at=last.effective_at, item_id=last.id)

    def get_by_id(self, news_id: int) -> NewsItem | None:
        stmt = select(NewsItem).where(NewsItem.id == news_id)
        return self.session.scalar(stmt)

    def get_article(self, news_id: int) -> ArticleContent | None:
        stmt = select(ArticleContent).where(ArticleContent.news_id == news_id)
        return self.session.scalar(stmt)

    def list_mentions(self, news_id: int) -> list[NewsStockMention]:
        stmt = select(NewsStockMention).where(NewsStockMention.news_id == news_id)
        return list(self.session.scalars(stmt))

    def get_topic_for_news(self, news_id: int) -> TopicCluster | None:
        stmt = (
            select(TopicCluster)
            .join(TopicNewsLink, TopicNewsLink.topic_cluster_id == TopicCluster.id)
            .where(TopicNewsLink.news_id == news_id)
        )
        return self.session.scalar(stmt)

    def get_detail_bundle(self, news_id: int) -> NewsDetailBundle | None:
        """详情页聚合读取:item/article/topic 单条 JOIN 查询 + mentions 一次列表查询。

        原实现为 4 次串行查询,SQLite 单 writer 场景下往返次数直接决定
        抽屉打开延迟,故合并为 2 次。

        一条新闻可能挂在多个 TopicNewsLink 上(ArticleContent × TopicNewsLink 产生
        笛卡尔行),旧实现直接 `.first()` 取到的是任意一条 topic——同一条新闻两次请求
        可能返回不同 topic。这里显式定序后取一条,规则为:
        importance_score 降序 → last_seen_at 降序 → topic id 降序,
        即“最重要、最新、最后创建”的那个 topic。SQLite 中 NULL 最小,DESC 时自动排在末尾,
        因此 importance_score/last_seen_at 为空的 topic 只会在没有更好候选时被选中。
        """
        stmt = (
            select(NewsItem, ArticleContent, TopicCluster)
            .outerjoin(ArticleContent, ArticleContent.news_id == NewsItem.id)
            .outerjoin(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
            .outerjoin(TopicCluster, TopicCluster.id == TopicNewsLink.topic_cluster_id)
            .where(NewsItem.id == news_id)
            .order_by(
                TopicCluster.importance_score.desc(),
                TopicCluster.last_seen_at.desc(),
                TopicCluster.id.desc(),
            )
            .limit(1)
        )
        row = self.session.execute(stmt).first()
        if row is None:
            return None
        item, article, topic = row
        return NewsDetailBundle(
            item=item,
            article=article,
            mentions=self.list_mentions(news_id),
            topic=topic,
        )

    def get_by_ids(self, news_ids: list[int]) -> list[NewsItem]:
        if not news_ids:
            return []
        stmt = select(NewsItem).where(NewsItem.id.in_(news_ids))
        return list(self.session.scalars(stmt))
