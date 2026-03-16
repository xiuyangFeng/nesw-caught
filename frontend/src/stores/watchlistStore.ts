import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import { HttpError } from '../api/http';
import type { NewsItem, WatchlistItem, WatchlistItemCreate } from '../types/api';
import { isStale } from '../utils/time';

export const useWatchlistStore = defineStore('watchlistStore', () => {
  const items = ref<WatchlistItem[]>([]);
  const relatedNews = ref<Record<string, NewsItem[]>>({});
  const selectedSymbol = ref<string | null>(null);
  const loading = ref(false);
  const relatedLoading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const createLoading = ref(false);
  const createError = ref<string | null>(null);

  const stale = computed(() => isStale(lastLoadedAt.value, 5));

  async function loadWatchlist() {
    loading.value = true;
    const response = await apiClient.getWatchlist();
    items.value = response.data;
    usingMock.value = response.degraded;
    lastLoadedAt.value = new Date().toISOString();
    if (!selectedSymbol.value && items.value.length > 0) {
      selectedSymbol.value = items.value[0].symbol;
    }
    loading.value = false;
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
      items.value = [...items.value, item].sort((left, right) => left.symbol.localeCompare(right.symbol));
      selectedSymbol.value = item.symbol;
      lastLoadedAt.value = new Date().toISOString();
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

  return {
    items,
    relatedNews,
    selectedSymbol,
    loading,
    relatedLoading,
    usingMock,
    lastLoadedAt,
    stale,
    createLoading,
    createError,
    loadWatchlist,
    loadRelatedNews,
    createWatchlist,
  };
});
