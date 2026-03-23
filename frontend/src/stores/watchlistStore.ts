import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import { HttpError } from '../api/http';
import { useRuntimeStatusStore } from './runtimeStatusStore';
import type {
  NewsItem,
  StockQuoteDetail,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistQuoteSummary,
} from '../types/api';
import { isStale } from '../utils/time';

export const useWatchlistStore = defineStore('watchlistStore', () => {
  const runtimeStatusStore = useRuntimeStatusStore();
  const candidates = ref<WatchlistCandidate[]>([]);
  const items = ref<WatchlistItem[]>([]);
  const quotes = ref<WatchlistQuoteSummary[]>([]);
  const quoteDetail = ref<StockQuoteDetail | null>(null);
  const relatedNews = ref<Record<string, NewsItem[]>>({});
  const lastManualRefreshResult = ref<import('../types/api').MarketRefreshResult | null>(null);
  const selectedSymbol = ref<string | null>(null);
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
    usingMock.value = response.degraded || quotesResponse.degraded;
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
    const response = await apiClient.getStockQuoteDetail(symbol);
    quoteDetail.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    lastLoadedAt.value = new Date().toISOString();
    detailLoading.value = false;
  }

  async function loadRelatedNews(symbol: string) {
    relatedLoading.value = true;
    selectedSymbol.value = symbol;
    const response = await apiClient.getRelatedNews(symbol);
    relatedNews.value[symbol] = response.data;
    usingMock.value = usingMock.value || response.degraded;
    relatedLoading.value = false;
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
    lastManualRefreshResult,
    selectedSymbol,
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
    createWatchlist,
    deleteWatchlist,
  };
});
