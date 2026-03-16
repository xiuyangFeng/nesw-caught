import type {
  HealthStatus,
  MarketSnapshot,
  NewsDetail,
  NewsItem,
  NewsQuery,
  StreamStatus,
  TopicDetail,
  TopicItem,
  WatchlistItem,
  WatchlistItemCreate,
  XAccount,
  XHealth,
  XPost,
  XPostQuery,
  XRefreshResult,
} from '../types/api';
import { getJson, postJson } from './http';
import {
  mockHealth,
  mockMarketSnapshots,
  mockNews,
  mockNewsDetails,
  mockRelatedNews,
  mockStreamStatus,
  mockTopicDetails,
  mockTopics,
  mockWatchlist,
  mockXAccounts,
  mockXHealth,
  mockXPosts,
  mockXRefreshResult,
} from './mock';

const withQuery = (base: string, query?: Record<string, string | number | undefined>) => {
  if (!query) {
    return base;
  }

  const search = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  });

  const suffix = search.toString();
  return suffix ? `${base}?${suffix}` : base;
};

async function withMockFallback<T>(request: () => Promise<T>, fallback: () => T): Promise<{ data: T; degraded: boolean }> {
  try {
    const data = await request();
    return { data, degraded: false };
  } catch {
    return { data: fallback(), degraded: true };
  }
}

export const apiClient = {
  getHealth() {
    return withMockFallback<HealthStatus>(() => getJson('/api/health'), () => mockHealth);
  },
  getNews(query: NewsQuery = {}) {
    return withMockFallback<NewsItem[]>(
      () => getJson(withQuery('/api/news', query)),
      () => {
        const filtered = mockNews.filter((item) => {
          const marketOk = !query.market || item.market === query.market;
          const sentimentOk = !query.sentiment_label || item.sentiment_label === query.sentiment_label;
          const sourceOk = !query.source_name || item.source_name === query.source_name;
          const searchText = query.q?.toLowerCase();
          const searchOk = !searchText || `${item.title} ${item.summary ?? ''}`.toLowerCase().includes(searchText);
          return marketOk && sentimentOk && sourceOk && searchOk;
        });
        return filtered.slice(0, query.limit ?? filtered.length);
      },
    );
  },
  getNewsDetail(id: number) {
    return withMockFallback<NewsDetail | null>(
      () => getJson(`/api/news/${id}`),
      () => mockNewsDetails[id] ?? null,
    );
  },
  getMarketSnapshots() {
    return withMockFallback<MarketSnapshot[]>(() => getJson('/api/market/snapshots'), () => mockMarketSnapshots);
  },
  getWatchlist() {
    return withMockFallback<WatchlistItem[]>(() => getJson('/api/watchlist'), () => mockWatchlist);
  },
  createWatchlist(payload: WatchlistItemCreate) {
    return postJson<WatchlistItem>('/api/watchlist', payload);
  },
  getRelatedNews(symbol: string) {
    return withMockFallback<NewsItem[]>(
      () => getJson(`/api/watchlist/${encodeURIComponent(symbol)}/related-news`),
      () => mockRelatedNews[symbol] ?? [],
    );
  },
  getTopics() {
    return withMockFallback<TopicItem[]>(() => getJson('/api/topics'), () => mockTopics);
  },
  getTopicDetail(id: number) {
    return withMockFallback<TopicDetail | null>(() => getJson(`/api/topics/${id}`), () => mockTopicDetails[id] ?? null);
  },
  getStreamStatus() {
    return withMockFallback<StreamStatus>(() => getJson('/api/stream/status'), () => mockStreamStatus);
  },
  getXHealth() {
    return withMockFallback<XHealth>(() => getJson('/api/health/x'), () => mockXHealth);
  },
  getXAccounts() {
    return withMockFallback<XAccount[]>(() => getJson('/api/x/accounts'), () => mockXAccounts);
  },
  getXPosts(query: XPostQuery = {}) {
    return withMockFallback<XPost[]>(
      () => getJson(withQuery('/api/x/posts', query)),
      () => {
        const filtered = mockXPosts.filter((item) => {
          const accountOk = !query.account_handle || item.account_handle === query.account_handle;
          const marketOk = !query.market || item.market === query.market;
          const searchText = query.q?.toLowerCase();
          const searchOk = !searchText || item.content_text.toLowerCase().includes(searchText);
          const symbolOk = !query.symbol || item.symbols.includes(query.symbol);
          return accountOk && marketOk && searchOk && symbolOk;
        });
        return filtered.slice(0, query.limit ?? filtered.length);
      },
    );
  },
  refreshXPosts() {
    return withMockFallback<XRefreshResult>(() => postJson('/api/x/refresh', {}), () => mockXRefreshResult);
  },
};
