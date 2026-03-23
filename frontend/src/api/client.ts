import type {
  FeishuNotifyConfig,
  FeishuNotifyConfigUpdate,
  FeishuTestResult,
  HealthStatus,
  LLMConnectionTestResponse,
  LLMConfigSummary,
  LLMConfigUpdateRequest,
  LLMTranslateRequest,
  LLMTranslateResponse,
  MarketSnapshot,
  StockKlineResponse,
  MarketRefreshResult,
  NewsAnalysis,
  NewsDetail,
  NewsItem,
  NewsQuery,
  NewsRefreshResult,
  WatchlistSparklineMap,
  StockQuoteDetail,
  StreamStatus,
  TopicDetail,
  TopicItem,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistQuoteSummary,
  XAccount,
  XHealth,
  XPost,
  XPostQuery,
  XRefreshResult,
} from '../types/api';
import { HttpError, deleteJson, getJson, postJson } from './http';
import {
  mockFeishuConfig,
  mockFeishuTestResult,
  mockHealth,
  mockLlmConfig,
  mockMarketSnapshots,
  mockNewsAnalyses,
  mockNews,
  mockNewsDetails,
  mockNewsRefreshResult,
  mockRelatedNews,
  mockStockQuoteDetails,
  mockStreamStatus,
  mockTopicDetails,
  mockTopics,
  mockWatchlistCandidates,
  mockWatchlist,
  mockWatchlistQuotes,
  mockWatchlistSparklines,
  buildMockTranslation,
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
  getLlmConfig() {
    return getJson<LLMConfigSummary>('/api/llm/config').then((data) => ({ data, degraded: false }));
  },
  saveLlmConfig(payload: LLMConfigUpdateRequest) {
    return postJson<LLMConfigSummary>('/api/llm/config', payload).then((data) => ({ data, degraded: false }));
  },
  testLlmConnection() {
    return postJson<LLMConnectionTestResponse>('/api/llm/test', {}).then((data) => ({ data, degraded: false }));
  },
  translateText(payload: LLMTranslateRequest) {
    return postJson<LLMTranslateResponse>('/api/llm/translate', payload)
      .then((data) => ({ data, degraded: false }))
      .catch((error) => {
        if (error instanceof HttpError) {
          throw error;
        }
        return { data: buildMockTranslation(payload.text), degraded: true };
      });
  },
  getNewsAnalysis(id: number) {
    return withMockFallback<NewsAnalysis | null>(
      () => getJson(`/api/news/${id}/analysis`),
      () => mockNewsAnalyses[id] ?? null,
    );
  },
  analyzeNews(id: number) {
    return withMockFallback<NewsAnalysis>(
      () => postJson(`/api/news/${id}/analyze`, {}),
      () => mockNewsAnalyses[id],
    );
  },
  refreshNews() {
    return withMockFallback<NewsRefreshResult>(() => postJson('/api/news/refresh', {}), () => mockNewsRefreshResult);
  },
  refreshMarketQuotes() {
    return withMockFallback<MarketRefreshResult>(
      () => postJson('/api/market/refresh', {}),
      () => ({
        quotes_count: mockWatchlistQuotes.length,
        symbols: mockWatchlistQuotes.map((item) => item.symbol),
        triggered_at: new Date().toISOString(),
      }),
    );
  },
  getMarketSnapshots() {
    return withMockFallback<MarketSnapshot[]>(() => getJson('/api/market/snapshots'), () => mockMarketSnapshots);
  },
  getWatchlistQuotes() {
    return withMockFallback<WatchlistQuoteSummary[]>(() => getJson('/api/market/watchlist'), () => mockWatchlistQuotes);
  },
  getStockQuoteDetail(symbol: string) {
    return withMockFallback<StockQuoteDetail | null>(
      () => getJson(`/api/market/symbols/${encodeURIComponent(symbol)}`),
      () => mockStockQuoteDetails[symbol] ?? null,
    );
  },
  getStockKline(symbol: string, interval: string, range: string) {
    return getJson<StockKlineResponse>(
      `/api/market/symbols/${encodeURIComponent(symbol)}/kline?interval=${encodeURIComponent(interval)}&range=${encodeURIComponent(range)}`,
    ).then((data) => ({ data, degraded: false }));
  },
  getWatchlistSparklines(symbols: string[]) {
    return withMockFallback<WatchlistSparklineMap>(
      () => postJson('/api/market/sparklines', { symbols }),
      () =>
        Object.fromEntries(
          symbols.map((symbol) => [symbol, mockWatchlistSparklines[symbol] ?? { prices: [] }]),
        ),
    );
  },
  getWatchlist() {
    return withMockFallback<WatchlistItem[]>(() => getJson('/api/watchlist'), () => mockWatchlist);
  },
  getWatchlistCandidates() {
    return withMockFallback<WatchlistCandidate[]>(() => getJson('/api/watchlist/candidates'), () => mockWatchlistCandidates);
  },
  createWatchlist(payload: WatchlistItemCreate) {
    return postJson<WatchlistItem>('/api/watchlist', payload);
  },
  deleteWatchlist(symbol: string) {
    return withMockFallback<void>(
      () => deleteJson(`/api/watchlist/${encodeURIComponent(symbol)}`),
      () => {
        const watchlistIndex = mockWatchlist.findIndex((item) => item.symbol === symbol);
        if (watchlistIndex >= 0) {
          mockWatchlist.splice(watchlistIndex, 1);
        }
        const quoteIndex = mockWatchlistQuotes.findIndex((item) => item.symbol === symbol);
        if (quoteIndex >= 0) {
          mockWatchlistQuotes.splice(quoteIndex, 1);
        }
      },
    );
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
  getXSearchResults(query: { q: string; limit?: number }) {
    return withMockFallback<XPost[]>(
      () => getJson(withQuery('/api/x/search', query)),
      () => {
        const searchText = query.q.toLowerCase();
        const filtered = mockXPosts.filter((item) => {
          return (
            item.content_text.toLowerCase().includes(searchText) ||
            item.symbols.some((symbol) => symbol.toLowerCase().includes(searchText))
          );
        });
        return filtered.slice(0, query.limit ?? filtered.length);
      },
    );
  },
  refreshXPosts() {
    return withMockFallback<XRefreshResult>(() => postJson('/api/x/refresh', {}), () => mockXRefreshResult);
  },
  getFeishuConfig() {
    return withMockFallback<FeishuNotifyConfig>(
      () => getJson('/api/notify/feishu/config'),
      () => mockFeishuConfig,
    );
  },
  saveFeishuConfig(payload: FeishuNotifyConfigUpdate) {
    return withMockFallback<FeishuNotifyConfig>(
      () => postJson('/api/notify/feishu/config', payload),
      () => {
        const updated = {
          ...mockFeishuConfig,
          configured: true,
          app_id: payload.app_id,
          app_secret_set: payload.app_secret ? true : mockFeishuConfig.app_secret_set,
          target_type: payload.target_type,
          target_id: payload.target_id,
          news_enabled: payload.news_enabled,
          news_keywords: payload.news_keywords ?? null,
          news_batch_interval_minutes: payload.news_batch_interval_minutes,
          alert_enabled: payload.alert_enabled,
          analysis_enabled: payload.analysis_enabled,
          is_active: payload.is_active,
          updated_at: new Date().toISOString(),
        };
        Object.assign(mockFeishuConfig, updated);
        return { ...mockFeishuConfig };
      },
    );
  },
  testFeishuNotify() {
    return withMockFallback<FeishuTestResult>(
      () => postJson('/api/notify/feishu/test', {}),
      () => mockFeishuTestResult,
    );
  },
};
