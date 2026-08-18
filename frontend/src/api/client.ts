import type {
  BacktestQuery,
  BacktestSummary,
  Digest,
  DigestLatest,
  FeishuNotifyConfig,
  FeishuNotifyConfigUpdate,
  FeishuTestResult,
  HealthStatus,
  LLMConnectionTestResponse,
  LLMConfigSummary,
  LLMConfigUpdateRequest,
  LLMStats,
  LLMTranslateRequest,
  LLMTranslateResponse,
  CalendarResponse,
  MarketSnapshot,
  StockKlineResponse,
  MarketRefreshResult,
  MarketIndexConfig,
  MarketIndexConfigCreate,
  MarketIndexConfigUpdate,
  MarketOverview,
  NewsAnalysis,
  NewsDetail,
  NewsEventDetail,
  NewsFeedLayout,
  NewsItem,
  NewsListPage,
  NewsQuery,
  NewsRuntimeStatus,
  NewsRefreshResult,
  NewsRefreshAcceptedResult,
  OpsHealth,
  PortfolioSummary,
  QuantDataStatus,
  QuantFundFlow,
  QuantRadar,
  QuantRecommendationLatest,
  QuantRecommendationRun,
  QuantResearchPack,
  QuantAiAudit,
  QuantProposal,
  QuantReportCard,
  QuantStrategy,
  QuantStrategyUpsert,
  QuantBacktest,
  QuantPaperAccount,
  QuantPaperOrder,
  QuantDecisionLog,
  QuantCopilotTools,
  WatchlistPositionUpdate,
  SentimentEvalResponse,
  SentimentTimelineResponse,
  WatchlistSparklineMap,
  StockQuoteDetail,
  StockResearchReport,
  StreamStatus,
  TopicDetail,
  TopicItem,
  WatchlistCandidate,
  WatchlistAiInsight,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistQuoteSummary,
  WatchlistResearchBrief,
  XAccount,
  XAccountCreatePayload,
  XAccountUpdatePayload,
  XAccountsExportResult,
  XAccountsImportResult,
  XHealth,
  XPost,
  XPostQuery,
  XRadarResponse,
  XRefreshResult,
} from '../types/api';
import { HttpError, deleteJson, getJson, isAbortError, patchJson, postJson } from './http';

type MockModule = typeof import('./mock');

const withQuery = (base: string, query?: Record<string, string | number | boolean | undefined>) => {
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

// Read-only endpoints may fall back to bundled mock data in dev builds so the
// UI stays usable without a backend. In production builds failures always
// propagate to the caller. Never use this helper for mutating requests
// (POST/PATCH/DELETE writes): a mock fallback would fake a successful write.
// The mock module is imported lazily so production bundles can tree-shake it.
async function withMockFallback<T>(
  request: () => Promise<T>,
  fallback: (mock: MockModule) => T,
): Promise<{ data: T; degraded: boolean }> {
  try {
    const data = await request();
    return { data, degraded: false };
  } catch (error) {
    // Aborted requests must propagate so callers can drop stale results;
    // falling back to mock would resurrect a request the caller cancelled.
    if (isAbortError(error)) {
      throw error;
    }
    // Mock module is only bundled in dev builds: this static `if` around the
    // dynamic import (rather than an early-return guard clause) lets Rollup
    // fold the branch away and tree-shake mock.ts out of production bundles
    // entirely. See sse.ts's createMockConnection for the same pattern.
    if (import.meta.env.DEV) {
      const mock = await import('./mock');
      return { data: fallback(mock), degraded: true };
    }
    throw error;
  }
}

export const apiClient = {
  getHealth() {
    return withMockFallback<HealthStatus>(() => getJson('/api/health'), (mock) => mock.mockHealth);
  },
  getNews(query: NewsQuery = {}, signal?: AbortSignal) {
    return withMockFallback<NewsListPage>(
      () => getJson(withQuery('/api/news', query), signal),
      (mock) => {
        const filtered = mock.mockNews.filter((item) => {
          const marketOk = !query.market || item.market === query.market;
          const sentimentOk = !query.sentiment_label || item.sentiment_label === query.sentiment_label;
          const sourceOk = !query.source_name || item.source_name === query.source_name;
          const searchText = query.q?.toLowerCase();
          const searchOk = !searchText || `${item.title} ${item.summary ?? ''}`.toLowerCase().includes(searchText);
          return marketOk && sentimentOk && sourceOk && searchOk;
        });
        const pageSize = query.limit ?? filtered.length;
        const cursorId = query.cursor?.split('|').pop();
        const startIndex = cursorId ? filtered.findIndex((item) => String(item.id) === cursorId) : -1;
        const sliceStart = startIndex >= 0 ? startIndex + 1 : 0;
        const items = filtered.slice(sliceStart, sliceStart + pageSize);
        const nextStart = sliceStart + pageSize;
        return {
          items,
          next_cursor: nextStart < filtered.length ? String(items.at(-1)?.id ?? '') : null,
        };
      },
    );
  },
  getNewsFeedLayout(query: { market?: string; limit_events?: number; limit_topics?: number; limit_stream?: number } = {}, signal?: AbortSignal) {
    return withMockFallback<NewsFeedLayout>(
      () => getJson(withQuery('/api/news/feed-layout', query), signal),
      (mock) => mock.mockNewsFeedLayout,
    );
  },
  getNewsEventDetail(eventKey: string) {
    return withMockFallback<NewsEventDetail>(
      () => getJson(`/api/news/events/${eventKey}`),
      (mock) => mock.mockNewsEventDetails[eventKey] ?? Object.values(mock.mockNewsEventDetails)[0],
    );
  },
  getNewsDetail(id: number) {
    return withMockFallback<NewsDetail | null>(
      () => getJson(`/api/news/${id}`),
      (mock) => mock.mockNewsDetails[id] ?? null,
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
  getAllLlmConfigs() {
    return withMockFallback<LLMConfigSummary[]>(
      () => getJson('/api/llm/config/all'),
      (mock) => mock.mockLlmConfigs,
    );
  },
  deleteLlmConfig(id: number) {
    return deleteJson(`/api/llm/config/${id}`).then((data) => ({ data, degraded: false }));
  },
  setDefaultLlmConfig(id: number) {
    return postJson<LLMConfigSummary>(`/api/llm/config/${id}/default`, {}).then((data) => ({ data, degraded: false }));
  },
  toggleLlmConfigActive(id: number, is_active: boolean) {
    return postJson<LLMConfigSummary>(withQuery(`/api/llm/config/${id}/active`, { is_active }), {}).then((data) => ({
      data,
      degraded: false,
    }));
  },
  getLlmStats() {
    return withMockFallback<LLMStats>(
      () => getJson('/api/llm/stats'),
      (mock) => mock.mockLlmStats,
    );
  },
  searchMarketSymbols(q: string) {
    return getJson<any[]>(`/api/market/search?q=${encodeURIComponent(q)}`).then((data) => ({ data, degraded: false }));
  },
  pingLlmConfig(id: number) {
    return postJson<LLMConnectionTestResponse & { latency_ms: number }>(`/api/llm/config/${id}/ping`, {}).then((data) => ({ data, degraded: false }));
  },
  translateText(payload: LLMTranslateRequest) {
    return postJson<LLMTranslateResponse>('/api/llm/translate', payload)
      .then((data) => ({ data, degraded: false }))
      .catch(async (error) => {
        if (error instanceof HttpError) {
          throw error;
        }
        // See withMockFallback above: the static DEV guard (rather than an
        // early-return guard clause) lets production builds tree-shake the
        // mock module out entirely.
        if (import.meta.env.DEV) {
          const { buildMockTranslation } = await import('./mock');
          return { data: buildMockTranslation(payload.text), degraded: true };
        }
        throw error;
      });
  },
  getNewsAnalysis(id: number) {
    return withMockFallback<NewsAnalysis | null>(
      () => getJson(`/api/news/${id}/analysis`),
      (mock) => mock.mockNewsAnalyses[id] ?? null,
    );
  },
  analyzeNews(id: number) {
    return postJson<NewsAnalysis>(`/api/news/${id}/analyze`, {}).then((data) => ({ data, degraded: false }));
  },
  refreshNews() {
    return postJson<NewsRefreshAcceptedResult>(withQuery('/api/news/refresh', { async_mode: true }), {}).then(
      (data) => ({ data, degraded: false }),
    );
  },
  getNewsRuntime() {
    return withMockFallback<NewsRuntimeStatus>(() => getJson('/api/news/runtime'), (mock) => mock.mockNewsRuntimeStatus);
  },
  refreshMarketQuotes() {
    return postJson<MarketRefreshResult>('/api/market/refresh', {}).then((data) => ({ data, degraded: false }));
  },
  getMarketSnapshots() {
    return withMockFallback<MarketSnapshot[]>(() => getJson('/api/market/snapshots'), (mock) => mock.mockMarketSnapshots);
  },
  getMarketOverview() {
    return withMockFallback<MarketOverview>(() => getJson('/api/market/overview'), (mock) => mock.mockMarketOverview);
  },
  getMarketIndexConfig() {
    return withMockFallback<MarketIndexConfig[]>(
      () => getJson('/api/market/index-config'),
      (mock) => mock.mockMarketIndexConfigs,
    );
  },
  createMarketIndexConfig(payload: MarketIndexConfigCreate) {
    return postJson<MarketIndexConfig>('/api/market/index-config', payload).then((data) => ({ data, degraded: false }));
  },
  updateMarketIndexConfig(id: number, payload: MarketIndexConfigUpdate) {
    return patchJson<MarketIndexConfig>(`/api/market/index-config/${id}`, payload).then((data) => ({
      data,
      degraded: false,
    }));
  },
  deleteMarketIndexConfig(id: number) {
    return deleteJson(`/api/market/index-config/${id}`).then((data) => ({ data, degraded: false }));
  },
  getWatchlistQuotes() {
    return withMockFallback<WatchlistQuoteSummary[]>(() => getJson('/api/market/watchlist'), (mock) => mock.mockWatchlistQuotes);
  },
  getStockQuoteDetail(symbol: string) {
    return withMockFallback<StockQuoteDetail | null>(
      () => getJson(`/api/market/symbols/${encodeURIComponent(symbol)}`),
      (mock) => mock.mockStockQuoteDetails[symbol] ?? null,
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
      (mock) =>
        Object.fromEntries(
          symbols.map((symbol) => [symbol, mock.mockWatchlistSparklines[symbol] ?? { prices: [] }]),
        ),
    );
  },
  getCalendar(days = 30) {
    return getJson<CalendarResponse>(withQuery('/api/calendar', { days })).then((data) => ({ data, degraded: false }));
  },
  getSymbolCalendar(symbol: string, days = 90) {
    return getJson<CalendarResponse>(withQuery(`/api/calendar/${encodeURIComponent(symbol)}`, { days })).then((data) => ({
      data,
      degraded: false,
    }));
  },
  getWatchlist() {
    return withMockFallback<WatchlistItem[]>(() => getJson('/api/watchlist'), (mock) => mock.mockWatchlist);
  },
  getWatchlistCandidates() {
    return withMockFallback<WatchlistCandidate[]>(() => getJson('/api/watchlist/candidates'), (mock) => mock.mockWatchlistCandidates);
  },
  createWatchlist(payload: WatchlistItemCreate) {
    return postJson<WatchlistItem>('/api/watchlist', payload);
  },
  deleteWatchlist(symbol: string) {
    return deleteJson(`/api/watchlist/${encodeURIComponent(symbol)}`).then((data) => ({ data, degraded: false }));
  },
  getRelatedNews(symbol: string) {
    return withMockFallback<NewsItem[]>(
      () => getJson(`/api/watchlist/${encodeURIComponent(symbol)}/related-news`),
      (mock) => mock.mockRelatedNews[symbol] ?? [],
    );
  },
  getSentimentTimeline(symbol: string, days = 30) {
    return withMockFallback<SentimentTimelineResponse>(
      () => getJson(withQuery(`/api/watchlist/${encodeURIComponent(symbol)}/sentiment-timeline`, { days })),
      (mock) => mock.mockSentimentTimelines[symbol] ?? mock.buildMockSentimentTimeline(symbol, days),
    );
  },
  getWatchlistResearchBrief(symbol: string) {
    return getJson<WatchlistResearchBrief>(`/api/watchlist/${encodeURIComponent(symbol)}/research-brief`).then((data) => ({
      data,
      degraded: false,
    }));
  },
  getStockResearch(symbol: string, lookbackDays?: number) {
    return getJson<StockResearchReport>(
      withQuery(`/api/research/stock/${encodeURIComponent(symbol)}`, { lookback_days: lookbackDays }),
    ).then((data) => ({ data, degraded: false }));
  },
  getWatchlistAiInsight(symbol: string) {
    return withMockFallback<WatchlistAiInsight>(
      () => postJson(`/api/watchlist/${encodeURIComponent(symbol)}/ai-insight`, {}),
      (mock) => mock.mockWatchlistAiInsights[symbol] ?? mock.buildMockWatchlistAiInsight(symbol),
    );
  },
  getPortfolio() {
    return getJson<PortfolioSummary>('/api/portfolio').then((data) => ({ data, degraded: false }));
  },
  setWatchlistPosition(symbol: string, payload: WatchlistPositionUpdate) {
    return patchJson<WatchlistItem>(`/api/watchlist/${encodeURIComponent(symbol)}`, payload).then((data) => ({
      data,
      degraded: false,
    }));
  },
  getTopics() {
    return withMockFallback<TopicItem[]>(() => getJson('/api/topics'), (mock) => mock.mockTopics);
  },
  getTopicDetail(id: number) {
    return withMockFallback<TopicDetail | null>(() => getJson(`/api/topics/${id}`), (mock) => mock.mockTopicDetails[id] ?? null);
  },
  getStreamStatus() {
    return withMockFallback<StreamStatus>(() => getJson('/api/stream/status'), (mock) => mock.mockStreamStatus);
  },
  getBacktestSummary(query: BacktestQuery = {}) {
    return getJson<BacktestSummary>(withQuery('/api/backtest', query)).then((data) => ({ data, degraded: false }));
  },
  getOpsHealth() {
    return getJson<OpsHealth>('/api/ops/health').then((data) => ({ data, degraded: false }));
  },
  getSentimentEval() {
    return withMockFallback<SentimentEvalResponse>(
      () => getJson('/api/eval/sentiment'),
      (mock) => mock.mockSentimentEval,
    );
  },
  runSentimentEval() {
    return withMockFallback<SentimentEvalResponse>(
      () => postJson('/api/eval/sentiment/run', {}),
      (mock) => mock.mockSentimentEval,
    );
  },
  getXHealth() {
    return withMockFallback<XHealth>(() => getJson('/api/health/x'), (mock) => mock.mockXHealth);
  },
  getXAccounts() {
    return withMockFallback<XAccount[]>(() => getJson('/api/x/accounts'), (mock) => mock.mockXAccounts);
  },
  getXRadar(limit = 50) {
    return withMockFallback<XRadarResponse>(() => getJson(`/api/x/radar?limit=${limit}`), (mock) => mock.mockXRadar);
  },
  createXAccount(payload: XAccountCreatePayload) {
    return postJson<XAccount>('/api/x/accounts', payload).then((data) => ({ data, degraded: false }));
  },
  updateXAccount(handle: string, payload: XAccountUpdatePayload) {
    return patchJson<XAccount>(`/api/x/accounts/${encodeURIComponent(handle)}`, payload).then((data) => ({
      data,
      degraded: false,
    }));
  },
  deleteXAccount(handle: string) {
    return deleteJson(`/api/x/accounts/${encodeURIComponent(handle)}`).then((data) => ({ data, degraded: false }));
  },
  importXAccounts() {
    return postJson<XAccountsImportResult>('/api/x/accounts/import', {}).then((data) => ({ data, degraded: false }));
  },
  exportXAccounts() {
    return postJson<XAccountsExportResult>('/api/x/accounts/export', {}).then((data) => ({ data, degraded: false }));
  },
  getXPosts(query: XPostQuery = {}) {
    return withMockFallback<XPost[]>(
      () => getJson(withQuery('/api/x/posts', query)),
      (mock) => {
        const filtered = mock.mockXPosts.filter((item) => {
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
      (mock) => {
        const searchText = query.q.toLowerCase();
        const filtered = mock.mockXPosts.filter((item) => {
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
    return postJson<XRefreshResult>('/api/x/refresh', {}).then((data) => ({ data, degraded: false }));
  },
  getFeishuConfig() {
    return withMockFallback<FeishuNotifyConfig>(
      () => getJson('/api/notify/feishu/config'),
      (mock) => mock.mockFeishuConfig,
    );
  },
  saveFeishuConfig(payload: FeishuNotifyConfigUpdate) {
    return postJson<FeishuNotifyConfig>('/api/notify/feishu/config', payload).then((data) => ({ data, degraded: false }));
  },
  testFeishuNotify() {
    return postJson<FeishuTestResult>('/api/notify/feishu/test', {}).then((data) => ({ data, degraded: false }));
  },
  getLatestDigest() {
    return getJson<DigestLatest>('/api/digest/latest').then((data) => ({ data, degraded: false }));
  },
  generateDigest(marketScope: string = 'all') {
    return postJson<Digest>(withQuery('/api/digest/generate', { market_scope: marketScope }), {}).then((data) => ({
      data,
      degraded: false,
    }));
  },
  getQuantLatest() {
    return withMockFallback<QuantRecommendationLatest>(
      () => getJson('/api/quant/recommendations/latest'),
      (mock) => mock.mockQuantLatest,
    );
  },
  runQuantRecommendations(scenario: 'abstain' | 'mixed' = 'abstain') {
    return postJson<QuantRecommendationLatest>('/api/quant/recommendations/run', { scenario, trigger: 'manual' }).then(
      (data) => ({ data, degraded: false }),
    );
  },
  getQuantDataStatus() {
    return withMockFallback<QuantDataStatus>(
      () => getJson('/api/quant/data/status'),
      (mock) => mock.mockQuantDataStatus,
    );
  },
  getQuantRadar() {
    return withMockFallback<QuantRadar>(() => getJson('/api/quant/radar'), (mock) => mock.mockQuantRadar);
  },
  getQuantFundFlow(symbol: string) {
    return withMockFallback<QuantFundFlow>(
      () => getJson(`/api/quant/symbols/${encodeURIComponent(symbol)}/fund-flow`),
      (mock) => ({ ...mock.mockQuantFundFlow, symbol }),
    );
  },
  getQuantResearch(symbol: string) {
    return withMockFallback<QuantResearchPack>(
      () => getJson(`/api/quant/symbols/${encodeURIComponent(symbol)}/research`),
      (mock) => ({ ...mock.mockQuantResearch, symbol }),
    );
  },
  getQuantAiAudit() {
    return withMockFallback<QuantAiAudit>(() => getJson('/api/quant/ai/audit'), (mock) => mock.mockQuantAiAudit);
  },
  getQuantRuns() {
    return withMockFallback<QuantRecommendationRun[]>(
      () => getJson('/api/quant/recommendations/runs'),
      (mock) => mock.mockQuantRuns,
    );
  },
  getQuantProposal() {
    return withMockFallback<QuantProposal>(
      () => getJson('/api/quant/portfolio-proposals/latest'),
      (mock) => mock.mockQuantProposal,
    );
  },
  getQuantReportCard(window = '30d') {
    return withMockFallback<QuantReportCard>(
      () => getJson(withQuery('/api/quant/report-card', { window })),
      (mock) => ({ ...mock.mockQuantReportCard, window }),
    );
  },
  getQuantStrategies() {
    return withMockFallback<QuantStrategy[]>(
      () => getJson('/api/quant/strategies'),
      (mock) => mock.mockQuantStrategies,
    );
  },
  createQuantStrategy(payload: QuantStrategyUpsert) {
    return postJson<QuantStrategy>('/api/quant/strategies', payload).then((data) => ({ data, degraded: false }));
  },
  previewQuantStrategy(payload: QuantStrategyUpsert) {
    return postJson<{ errors: string[]; hit: boolean }>('/api/quant/strategies/preview', payload).then((data) => ({
      data,
      degraded: false,
    }));
  },
  runQuantBacktest(payload: QuantStrategyUpsert) {
    return postJson<QuantBacktest>('/api/quant/backtests', payload).then((data) => ({ data, degraded: false }));
  },
  getQuantPaperAccount() {
    return withMockFallback<QuantPaperAccount>(
      () => getJson('/api/quant/paper/account'),
      (mock) => mock.mockQuantPaperAccount,
    );
  },
  placeQuantPaperOrder(payload: { symbol: string; side?: string; quantity?: number; confirmed?: boolean }) {
    return postJson<QuantPaperOrder>('/api/quant/paper/orders', payload).then((data) => ({ data, degraded: false }));
  },
  getQuantDecisionLog() {
    return withMockFallback<QuantDecisionLog>(
      () => getJson('/api/quant/decision-log'),
      (mock) => mock.mockQuantDecisionLog,
    );
  },
  getQuantCopilotTools() {
    return withMockFallback<QuantCopilotTools>(
      () => getJson('/api/quant/copilot/tools'),
      (mock) => mock.mockQuantCopilotTools,
    );
  },
};
