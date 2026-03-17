import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { NewsAnalysis, NewsDetail, NewsItem, NewsQuery } from '../types/api';
import { isStale } from '../utils/time';

export const useNewsStore = defineStore('newsStore', () => {
  const items = ref<NewsItem[]>([]);
  const detailMap = ref<Record<number, NewsDetail | null>>({});
  const analysisMap = ref<Record<number, NewsAnalysis | null>>({});
  const analysisLoadingMap = ref<Record<number, boolean>>({});
  const analysisErrorMap = ref<Record<number, string | null>>({});
  const loading = ref(false);
  const detailLoading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const activeQuery = ref<NewsQuery>({ limit: 200 });

  const stale = computed(() => isStale(lastLoadedAt.value, 5));

  async function loadNews(query: NewsQuery = activeQuery.value) {
    loading.value = true;
    activeQuery.value = { ...query };
    const response = await apiClient.getNews(activeQuery.value);
    items.value = response.data;
    usingMock.value = response.degraded;
    lastLoadedAt.value = new Date().toISOString();
    loading.value = false;
  }

  async function loadDetail(id: number) {
    detailLoading.value = true;
    const response = await apiClient.getNewsDetail(id);
    detailMap.value[id] = response.data;
    usingMock.value = usingMock.value || response.degraded;
    detailLoading.value = false;
  }

  async function loadAnalysis(id: number) {
    analysisLoadingMap.value[id] = true;
    analysisErrorMap.value[id] = null;
    try {
      const response = await apiClient.getNewsAnalysis(id);
      analysisMap.value[id] = response.data;
      usingMock.value = usingMock.value || response.degraded;
    } catch (error) {
      analysisErrorMap.value[id] = error instanceof Error ? error.message : '加载分析结果失败';
      analysisMap.value[id] = null;
    } finally {
      analysisLoadingMap.value[id] = false;
    }
  }

  async function analyzeNews(id: number) {
    analysisLoadingMap.value[id] = true;
    analysisErrorMap.value[id] = null;
    try {
      const response = await apiClient.analyzeNews(id);
      analysisMap.value[id] = response.data;
      usingMock.value = usingMock.value || response.degraded;
      return response.data;
    } catch (error) {
      analysisErrorMap.value[id] = error instanceof Error ? error.message : '分析失败';
      throw error;
    } finally {
      analysisLoadingMap.value[id] = false;
    }
  }

  async function refreshNews() {
    const response = await apiClient.refreshNews();
    usingMock.value = usingMock.value || response.degraded;
    if (response.degraded) {
      return false;
    }

    await loadNews(activeQuery.value);
    return true;
  }

  function upsertNews(item: NewsItem) {
    const existingIndex = items.value.findIndex((candidate) => candidate.id === item.id);
    if (existingIndex >= 0) {
      items.value.splice(existingIndex, 1, item);
    } else {
      items.value.unshift(item);
    }
    lastLoadedAt.value = new Date().toISOString();
  }

  return {
    items,
    detailMap,
    analysisMap,
    analysisLoadingMap,
    analysisErrorMap,
    loading,
    detailLoading,
    usingMock,
    lastLoadedAt,
    stale,
    activeQuery,
    loadNews,
    loadDetail,
    loadAnalysis,
    analyzeNews,
    refreshNews,
    upsertNews,
  };
});
