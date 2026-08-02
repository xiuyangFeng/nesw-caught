from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.google_news_search import GoogleNewsSearchClient, GoogleNewsSearchError
from app.services.ingestion.dedup_gate import normalize_url_for_hash
from app.services.news_ingestion import SourceItem
from app.services.tavily_client import TavilyClient, TavilyClientError

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _build_default_queries(symbol: str, display_name: str, market: str) -> list[str]:
    queries = [f"{display_name} {symbol} stock news"]
    if market in ("cn", "hk") and not _is_cjk(display_name):
        queries.append(f"{display_name} {symbol} 股票 新闻")
    elif _is_cjk(display_name):
        queries.append(f"{display_name} 最新消息")
    return queries


def _is_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _language_for_market(market: str) -> str:
    return "zh" if market in ("cn", "hk") else "en"


_search_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stock-news-search")


class StockNewsSearchService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def sync_match_existing(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> int:
        keywords = [symbol.upper()]
        if display_name and display_name.upper() != symbol.upper():
            keywords.append(display_name)

        conditions = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(NewsItem.title.like(pattern))
            conditions.append(NewsItem.summary.like(pattern))

        stmt = (
            select(NewsItem)
            .where(or_(*conditions))
            .order_by(
                NewsItem.published_at.is_(None).asc(),
                NewsItem.published_at.desc(),
                NewsItem.fetched_at.desc(),
            )
            .limit(20)
        )
        matched_news = list(self.session.scalars(stmt))

        created_count = 0
        for news_item in matched_news:
            existing = self.session.scalar(
                select(NewsStockMention).where(
                    NewsStockMention.news_id == news_item.id,
                    NewsStockMention.symbol == symbol.upper(),
                )
            )
            if existing is None:
                self.session.add(
                    NewsStockMention(
                        news_id=news_item.id,
                        symbol=symbol.upper(),
                        market=market,
                        mention_type="keyword_match",
                        confidence=0.6,
                    )
                )
                created_count += 1

        if created_count > 0:
            # 只 flush 不提交：与调用方（如 watchlist 创建）处于同一请求事务，
            # 由请求边界统一 commit/rollback，保证组合操作原子性。
            self.session.flush()
        return len(matched_news)

    def trigger_async_external_search(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> None:
        _search_executor.submit(
            self._run_external_search,
            symbol,
            display_name,
            market,
        )

    def _run_external_search(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> None:
        try:
            with SessionLocal() as session:
                service = _ExternalSearchWorker(session)
                service.search_and_persist(symbol, display_name, market)
        except Exception:
            logger.exception("async external news search failed for %s (%s)", symbol, display_name)


class _ExternalSearchWorker:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def search_and_persist(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> int:
        queries = self._build_queries(symbol, display_name, market)
        all_items: list[SourceItem] = []

        def _fetch_query(query: str) -> list[SourceItem]:
            items = self._search_tavily(query)
            if not items:
                items = self._search_google_news(query, market)
            return items

        # 并发多 Query 检索加速
        if len(queries) > 1:
            with ThreadPoolExecutor(max_workers=min(len(queries), 4)) as pool:
                for items in pool.map(_fetch_query, queries):
                    all_items.extend(items)
        else:
            for query in queries:
                all_items.extend(_fetch_query(query))

        persisted_count = 0
        seen_hashes: set[str] = set()
        for item in all_items:
            # 与 persister.persist_item 保持同一套 URL 归一化：否则同一篇文章经
            # 搜索路径落库时算出的 hash 与抓取路径不同，唯一闸失效 → 重复插入。
            url_hash = sha256(normalize_url_for_hash(item.canonical_url).encode("utf-8")).hexdigest()
            if url_hash in seen_hashes:
                continue
            seen_hashes.add(url_hash)
            news_id = self._persist_news_item(item, market, url_hash)
            if news_id is not None:
                self._ensure_mention(news_id, symbol, market)
                persisted_count += 1

        if persisted_count > 0:
            self.session.commit()
        logger.info(
            "external search for %s (%s): %d queries, %d results, %d persisted",
            symbol, display_name, len(queries), len(all_items), persisted_count,
        )
        return persisted_count

    def _build_queries(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> list[str]:
        queries = _build_default_queries(symbol, display_name, market)

        llm_keywords = self._try_llm_expand(symbol, display_name, market)
        if llm_keywords:
            queries = [f"{' '.join(llm_keywords)} latest news"] + queries

        return queries[:3]

    def _try_llm_expand(
        self,
        symbol: str,
        display_name: str,
        market: str,
    ) -> list[str] | None:
        try:
            config_repo = LLMProviderConfigRepository(self.session)
            config = config_repo.get_active()
            if config is None:
                return None

            prompt = (
                f"Given stock symbol '{symbol}' (market: {market}, display name: '{display_name}'), "
                f"generate a JSON array of 3-5 search keywords or aliases for finding recent news about this company. "
                f"Include the company's full official name, common abbreviations, and Chinese name if applicable. "
                f"Return ONLY a JSON array of strings, e.g. [\"Apple Inc\", \"AAPL\", \"苹果公司\"]"
            )

            base_url = (config.base_url or "").rstrip("/")
            if not base_url or not config.decrypted_api_key:
                return None

            from app.services import http_pool

            client = http_pool.get_feed_client()
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.decrypted_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model_name,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that returns only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
                timeout=15.0,
            )
            if response.status_code >= 400:
                return None

            payload = response.json()
            choices = payload.get("choices", [])
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content", "")
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return [str(k) for k in parsed if isinstance(k, str)][:5]
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        return [str(k) for k in v if isinstance(k, str)][:5]
            return None
        except Exception:
            logger.warning("LLM keyword expansion failed for %s, falling back to defaults", symbol)
            return None

    def _search_tavily(self, query: str) -> list[SourceItem]:
        if not self.settings.tavily_api_key:
            return []
        try:
            client = TavilyClient(self.settings.tavily_api_key)
            return client.search_news(query, max_results=5)
        except TavilyClientError as exc:
            logger.warning("tavily search failed for query: %s (%s)", query, exc)
            return []

    def _search_google_news(self, query: str, market: str) -> list[SourceItem]:
        try:
            client = GoogleNewsSearchClient()
            lang = _language_for_market(market)
            return client.search_news(query, max_results=8, language=lang)
        except GoogleNewsSearchError as exc:
            logger.warning("google news search failed for query: %s (%s)", query, exc)
            return []

    def _persist_news_item(self, item: SourceItem, market: str, url_hash: str) -> int | None:
        existing = self.session.scalar(
            select(NewsItem).where(NewsItem.url_hash == url_hash)
        )
        if existing is not None:
            return existing.id

        news_item = NewsItem(
            source_name="web_search",
            source_url=item.canonical_url,
            title=item.title[:500],
            summary=item.summary,
            canonical_url=item.canonical_url,
            url_hash=url_hash,
            market=market,
            language=None,
            sentiment_label=None,
            sentiment_score=None,
            published_at=item.published_at,
            fetched_at=_utc_now(),
            ingest_status="search_result",
        )
        self.session.add(news_item)
        self.session.flush()

        if item.content_text:
            self.session.add(
                ArticleContent(
                    news_id=news_item.id,
                    content_text=item.content_text,
                    content_html=None,
                    extract_status="success",
                    extract_error=None,
                    extracted_at=_utc_now(),
                )
            )
        return news_item.id

    def _ensure_mention(self, news_id: int, symbol: str, market: str) -> None:
        existing = self.session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news_id,
                NewsStockMention.symbol == symbol.upper(),
            )
        )
        if existing is None:
            self.session.add(
                NewsStockMention(
                    news_id=news_id,
                    symbol=symbol.upper(),
                    market=market,
                    mention_type="search_result",
                    confidence=0.7,
                )
            )
