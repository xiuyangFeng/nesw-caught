import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import { HttpError } from '../api/http';
import { useRuntimeStatusStore } from './runtimeStatusStore';
import type {
  LlmFailoverInfo,
  NewsItem,
  StockKlineResponse,
  StockQuoteDetail,
  WatchlistDashboardPeriod,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistQuoteSummary,
  WatchlistResearchBrief,
} from '../types/api';
import { isStale } from '../utils/time';

// 后端 WatchlistAiInsightView.failover 是无结构 dict[str, str],
// 这里做运行时校验并窄化为前端约定的 LlmFailoverInfo。
function toFailoverInfo(raw: Record<string, string> | null | undefined): LlmFailoverInfo | null {
  if (raw && typeof raw.from_model === 'string' && typeof raw.to_model === 'string') {
    return { from_model: raw.from_model, to_model: raw.to_model, reason: raw.reason ?? '' };
  }
  return null;
}

const PERIOD_QUERY_MAP: Record<WatchlistDashboardPeriod, { interval: string; range: string }> = {
  '1D': { interval: '1d', range: '1y' },
  '1W': { interval: '1wk', range: '5y' },
  '1M': { interval: '1mo', range: '10y' },
  '1Y': { interval: '1mo', range: 'max' },
};

export const useWatchlistStore = defineStore('watchlistStore', () => {
  const runtimeStatusStore = useRuntimeStatusStore();
  const candidates = ref<WatchlistCandidate[]>([]);
  const items = ref<WatchlistItem[]>([]);
  const quotes = ref<WatchlistQuoteSummary[]>([]);
  const quoteDetail = ref<StockQuoteDetail | null>(null);
  const relatedNews = ref<Record<string, NewsItem[]>>({});
  const detailNews = ref<NewsItem[]>([]);
  const researchBrief = ref<WatchlistResearchBrief | null>(null);
  const aiInsights = ref<Record<string, { loading: boolean; text: string | null; error: string | null; failover?: { from_model: string; to_model: string; reason: string } | null }>>({});
  const lastManualRefreshResult = ref<import('../types/api').MarketRefreshResult | null>(null);
  const selectedSymbol = ref<string | null>(null);
  const currentPeriod = ref<WatchlistDashboardPeriod>('1D');
  const currentInterval = ref('1d');
  const currentRange = ref('1y');
  const klineData = ref<StockKlineResponse | null>(null);
  const klineLoading = ref(false);
  const klineError = ref<string | null>(null);
  const sparklines = ref<Record<string, number[]>>({});
  const selectedCandidate = ref<WatchlistCandidate | null>(null);
  const loading = ref(false);
  const relatedLoading = ref(false);
  const detailLoading = ref(false);
  const refreshLoading = ref(false);
  const candidatesLoading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const createLoading = ref(false);
  const createError = ref<string | null>(null);
  const refreshError = ref<string | null>(null);
  const deleteLoadingSymbol = ref<string | null>(null);
  const deleteError = ref<string | null>(null);
  const candidateError = ref<string | null>(null);
  let detailRequestId = 0;

  const stale = computed(() => isStale(lastLoadedAt.value, 5));

  function beginDetailRequest(symbol: string): number {
    detailRequestId += 1;
    selectedSymbol.value = symbol;
    detailNews.value = [];
    researchBrief.value = null;
    klineData.value = null;
    klineError.value = null;
    quoteDetail.value = null;
    return detailRequestId;
  }

  async function loadCandidates() {
    candidatesLoading.value = true;
    candidateError.value = null;
    try {
      const response = await apiClient.getWatchlistCandidates();
      candidates.value = response.data;
      usingMock.value = usingMock.value || response.degraded;
    } catch {
      candidateError.value = '股票候选加载失败，请检查后端服务';
      throw new Error(candidateError.value);
    } finally {
      candidatesLoading.value = false;
    }
  }

  async function loadWatchlist() {
    loading.value = true;
    const response = await apiClient.getWatchlist();
    items.value = response.data;
    const quotesResponse = await apiClient.getWatchlistQuotes();
    quotes.value = quotesResponse.data;
    const symbols = items.value.map((item) => item.symbol);
    let sparklineResponse: Awaited<ReturnType<typeof apiClient.getWatchlistSparklines>> | { data: {}; degraded: false } = {
      data: {},
      degraded: false,
    };
    if (symbols.length) {
      try {
        sparklineResponse = await apiClient.getWatchlistSparklines(symbols);
      } catch {
        sparklineResponse = { data: {}, degraded: false };
      }
    }
    const sparklineData = sparklineResponse?.data ?? {};
    // 后端 SparklineSeriesView.prices 为可选字段(缺省即空序列),兜底为空数组
    sparklines.value = Object.fromEntries(
      Object.entries(sparklineData).map(([symbol, series]) => [symbol, series.prices ?? []]),
    );
    usingMock.value = response.degraded || quotesResponse.degraded || Boolean(sparklineResponse?.degraded);
    lastLoadedAt.value = new Date().toISOString();
    if (!selectedSymbol.value && items.value.length > 0) {
      selectedSymbol.value = items.value[0].symbol;
    }
    loading.value = false;
  }

  async function refreshMarketQuotes() {
    refreshLoading.value = true;
    refreshError.value = null;
    try {
      const response = await apiClient.refreshMarketQuotes();
      usingMock.value = usingMock.value || response.degraded;
      lastManualRefreshResult.value = response.data;
      await loadWatchlist();
      await runtimeStatusStore.loadRuntimeStatus();
    } catch (error) {
      refreshError.value = '手动刷新行情失败，请稍后重试';
      throw error;
    } finally {
      refreshLoading.value = false;
    }
  }

  async function loadQuoteDetail(symbol: string, requestId = detailRequestId) {
    detailLoading.value = true;
    try {
      const response = await apiClient.getStockQuoteDetail(symbol);
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        quoteDetail.value = response.data;
        usingMock.value = usingMock.value || response.degraded;
        lastLoadedAt.value = new Date().toISOString();
      }
    } finally {
      if (requestId === detailRequestId) {
        detailLoading.value = false;
      }
    }
  }

  async function loadRelatedNews(symbol: string, requestId = detailRequestId) {
    relatedLoading.value = true;
    try {
      const response = await apiClient.getRelatedNews(symbol);
      relatedNews.value[symbol] = response.data;
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        detailNews.value = response.data;
      }
      usingMock.value = usingMock.value || response.degraded;
    } finally {
      if (requestId === detailRequestId) {
        relatedLoading.value = false;
      }
    }
  }

  async function loadResearchBrief(symbol: string, requestId = detailRequestId) {
    try {
      const response = await apiClient.getWatchlistResearchBrief(symbol);
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        researchBrief.value = response.data;
      }
      usingMock.value = usingMock.value || response.degraded;
    } catch {
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        researchBrief.value = null;
      }
    }
  }

  async function loadKline(symbol: string, period = currentPeriod.value, requestId = detailRequestId) {
    const query = PERIOD_QUERY_MAP[period];
    klineLoading.value = true;
    klineError.value = null;
    currentPeriod.value = period;
    currentInterval.value = query.interval;
    currentRange.value = query.range;
    try {
      const response = await apiClient.getStockKline(symbol, query.interval, query.range);
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        klineData.value = response.data;
      }
      usingMock.value = usingMock.value || response.degraded;
    } catch {
      if (requestId === detailRequestId && selectedSymbol.value === symbol) {
        klineData.value = null;
        klineError.value = 'K 线数据加载失败，请稍后重试';
      }
    } finally {
      if (requestId === detailRequestId) {
        klineLoading.value = false;
      }
    }
  }

  async function selectSymbol(symbol: string) {
    const requestId = beginDetailRequest(symbol);
    const [, newsResult] = await Promise.allSettled([
      loadKline(symbol, currentPeriod.value, requestId),
      loadRelatedNews(symbol, requestId),
      loadResearchBrief(symbol, requestId),
    ]);
    if (newsResult.status === 'rejected') {
      detailNews.value = [];
    }
  }

  async function loadDetailWorkspace(symbol: string) {
    const requestId = beginDetailRequest(symbol);
    const [, newsResult] = await Promise.allSettled([
      loadQuoteDetail(symbol, requestId),
      loadKline(symbol, currentPeriod.value, requestId),
      loadRelatedNews(symbol, requestId),
      loadResearchBrief(symbol, requestId),
    ]);
    if (newsResult.status === 'rejected') {
      detailNews.value = [];
    }
    if (
      quoteDetail.value?.symbol === symbol &&
      !quoteDetail.value.display_name &&
      (quoteDetail.value.status === 'unavailable' || quoteDetail.value.status === 'symbol_not_supported')
    ) {
      throw new HttpError('watchlist symbol not found', 404);
    }
  }

  async function switchPeriod(period: WatchlistDashboardPeriod) {
    if (!selectedSymbol.value) {
      return;
    }
    detailRequestId += 1;
    await loadKline(selectedSymbol.value, period);
  }

  async function createWatchlist(payload: WatchlistItemCreate) {
    createLoading.value = true;
    createError.value = null;
    try {
      const item = await apiClient.createWatchlist(payload);
      selectedSymbol.value = item.symbol;
      await loadWatchlist();
      await loadRelatedNews(item.symbol);
    } catch (error) {
      if (error instanceof HttpError && error.status === 409) {
        createError.value = '该股票已经在自选股列表中';
      } else {
        createError.value = '添加自选股失败，请检查后端服务';
      }
      throw error;
    } finally {
      createLoading.value = false;
    }
  }

  async function deleteWatchlist(symbol: string) {
    deleteLoadingSymbol.value = symbol;
    deleteError.value = null;
    try {
      await apiClient.deleteWatchlist(symbol);
      delete relatedNews.value[symbol];
      await loadWatchlist();
      if (selectedSymbol.value === symbol) {
        selectedSymbol.value = items.value[0]?.symbol ?? null;
      }
      if (!selectedSymbol.value) {
        quoteDetail.value = null;
        klineData.value = null;
        klineError.value = null;
        detailNews.value = [];
        researchBrief.value = null;
      }
    } catch {
      deleteError.value = '删除自选股失败，请检查后端服务';
      throw new Error(deleteError.value);
    } finally {
      deleteLoadingSymbol.value = null;
    }
  }

  async function loadAiInsight(symbol: string) {
    aiInsights.value[symbol] = { loading: true, text: null, error: null, failover: null };
    try {
      const response = await apiClient.getWatchlistAiInsight(symbol);
      aiInsights.value[symbol] = {
        loading: false,
        text: response.data.insight_text,
        error: null,
        failover: toFailoverInfo(response.data.failover),
      };
    } catch (error) {
      aiInsights.value[symbol] = {
        loading: false,
        text: null,
        error: error instanceof Error ? error.message : '获取 AI 研判失败',
        failover: null,
      };
    }
  }

  return {
    candidates,
    items,
    quotes,
    quoteDetail,
    relatedNews,
    detailNews,
    researchBrief,
    aiInsights,
    lastManualRefreshResult,
    selectedSymbol,
    currentPeriod,
    currentInterval,
    currentRange,
    klineData,
    klineLoading,
    klineError,
    sparklines,
    selectedCandidate,
    loading,
    relatedLoading,
    detailLoading,
    refreshLoading,
    candidatesLoading,
    usingMock,
    lastLoadedAt,
    stale,
    createLoading,
    createError,
    refreshError,
    deleteLoadingSymbol,
    deleteError,
    candidateError,
    loadCandidates,
    loadWatchlist,
    refreshMarketQuotes,
    loadQuoteDetail,
    loadRelatedNews,
    loadResearchBrief,
    loadKline,
    selectSymbol,
    loadDetailWorkspace,
    switchPeriod,
    createWatchlist,
    deleteWatchlist,
    loadAiInsight,
  };
});
