import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import { HttpError } from '../api/http';
import { useRuntimeStatusStore } from './runtimeStatusStore';
import type {
  NewsItem,
  StockKlineResponse,
  StockQuoteDetail,
  WatchlistDashboardPeriod,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistQuoteSummary,
} from '../types/api';
import { isStale } from '../utils/time';

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
    sparklines.value = Object.fromEntries(Object.entries(sparklineData).map(([symbol, series]) => [symbol, series.prices]));
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

  async function loadQuoteDetail(symbol: string) {
    detailLoading.value = true;
    selectedSymbol.value = symbol;
    quoteDetail.value = null;
    try {
      const response = await apiClient.getStockQuoteDetail(symbol);
      quoteDetail.value = response.data;
      usingMock.value = usingMock.value || response.degraded;
      lastLoadedAt.value = new Date().toISOString();
    } finally {
      detailLoading.value = false;
    }
  }

  async function loadRelatedNews(symbol: string) {
    relatedLoading.value = true;
    const requestId = detailRequestId;
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

  async function loadKline(symbol: string, period = currentPeriod.value) {
    const requestId = detailRequestId;
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
    detailRequestId += 1;
    selectedSymbol.value = symbol;
    detailNews.value = [];
    klineData.value = null;
    klineError.value = null;
    const [, newsResult] = await Promise.allSettled([loadKline(symbol, currentPeriod.value), loadRelatedNews(symbol)]);
    if (newsResult.status === 'rejected') {
      detailNews.value = [];
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
      }
    } catch {
      deleteError.value = '删除自选股失败，请检查后端服务';
      throw new Error(deleteError.value);
    } finally {
      deleteLoadingSymbol.value = null;
    }
  }

  return {
    candidates,
    items,
    quotes,
    quoteDetail,
    relatedNews,
    detailNews,
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
    loadKline,
    selectSymbol,
    switchPeriod,
    createWatchlist,
    deleteWatchlist,
  };
});
