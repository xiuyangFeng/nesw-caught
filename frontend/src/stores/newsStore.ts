import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { NewsDetail, NewsItem, NewsQuery } from '../types/api';
import { isStale } from '../utils/time';

export const useNewsStore = defineStore('newsStore', () => {
  const items = ref<NewsItem[]>([]);
  const detailMap = ref<Record<number, NewsDetail | null>>({});
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
    loading,
    detailLoading,
    usingMock,
    lastLoadedAt,
    stale,
    activeQuery,
    loadNews,
    loadDetail,
    refreshNews,
    upsertNews,
  };
});
