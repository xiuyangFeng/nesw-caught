import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { NewsAnalysis, NewsDetail, NewsItem, NewsQuery } from '../types/api';
import { isStale } from '../utils/time';

export const useNewsStore = defineStore('newsStore', () => {
  const detailMap = ref<Record<number, NewsDetail | null>>({});
  const analysisMap = ref<Record<number, NewsAnalysis | null>>({});
  const analysisLoadingMap = ref<Record<number, boolean>>({});
  const analysisErrorMap = ref<Record<number, string | null>>({});
  const detailLoading = ref(false);
  const usingMock = ref(false);

  const dashboardItems = ref<NewsItem[]>([]);
  const dashboardLoading = ref(false);
  const dashboardLastLoadedAt = ref<string | null>(null);
  const dashboardQuery = ref<NewsQuery>({ limit: 200 });

  const feedItems = ref<NewsItem[]>([]);
  const feedLoading = ref(false);
  const feedLastLoadedAt = ref<string | null>(null);
  const feedQuery = ref<NewsQuery>({ limit: 300 });

  const sentimentItems = ref<NewsItem[]>([]);
  const sentimentLoading = ref(false);
  const sentimentLastLoadedAt = ref<string | null>(null);
  const sentimentQuery = ref<NewsQuery>({ limit: 300 });

  const dashboardStale = computed(() => isStale(dashboardLastLoadedAt.value, 5));
  const feedStale = computed(() => isStale(feedLastLoadedAt.value, 5));
  const sentimentStale = computed(() => isStale(sentimentLastLoadedAt.value, 5));
  const stale = computed(() => dashboardStale.value || feedStale.value || sentimentStale.value);

  function matchesQuery(item: NewsItem, query: NewsQuery) {
    if (query.market && item.market !== query.market) {
      return false;
    }
    if (query.sentiment_label && item.sentiment_label !== query.sentiment_label) {
      return false;
    }
    if (query.source_name && item.source_name !== query.source_name) {
      return false;
    }
    if (query.q) {
      const haystack = `${item.title} ${item.summary ?? ''}`.toLowerCase();
      if (!haystack.includes(query.q.toLowerCase())) {
        return false;
      }
    }
    return true;
  }

  async function loadScopedNews(
    query: NewsQuery,
    options: {
      items: typeof dashboardItems;
      loading: typeof dashboardLoading;
      lastLoadedAt: typeof dashboardLastLoadedAt;
      queryRef: typeof dashboardQuery;
    },
  ) {
    options.loading.value = true;
    options.queryRef.value = { ...query };
    const response = await apiClient.getNews(options.queryRef.value);
    options.items.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    options.lastLoadedAt.value = new Date().toISOString();
    options.loading.value = false;
  }

  async function loadDashboardNews(query: NewsQuery = dashboardQuery.value) {
    await loadScopedNews(query, {
      items: dashboardItems,
      loading: dashboardLoading,
      lastLoadedAt: dashboardLastLoadedAt,
      queryRef: dashboardQuery,
    });
  }

  async function loadFeedNews(query: NewsQuery = feedQuery.value) {
    await loadScopedNews(query, {
      items: feedItems,
      loading: feedLoading,
      lastLoadedAt: feedLastLoadedAt,
      queryRef: feedQuery,
    });
  }

  async function loadSentimentNews(query: NewsQuery = sentimentQuery.value) {
    await loadScopedNews(query, {
      items: sentimentItems,
      loading: sentimentLoading,
      lastLoadedAt: sentimentLastLoadedAt,
      queryRef: sentimentQuery,
    });
  }

  function upsertScopedItems(itemsRef: typeof dashboardItems, query: NewsQuery, item: NewsItem) {
    if (!matchesQuery(item, query)) {
      return;
    }

    const existingIndex = itemsRef.value.findIndex((candidate) => candidate.id === item.id);
    if (existingIndex >= 0) {
      itemsRef.value.splice(existingIndex, 1, item);
    } else {
      itemsRef.value.unshift(item);
      const limit = query.limit ?? itemsRef.value.length;
      if (itemsRef.value.length > limit) {
        itemsRef.value.length = limit;
      }
    }
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
    return refreshDashboardNews();
  }

  async function refreshDashboardNews() {
    const response = await apiClient.refreshNews();
    usingMock.value = usingMock.value || response.degraded;
    if (response.degraded) {
      return false;
    }

    await loadDashboardNews(dashboardQuery.value);
    return true;
  }

  function upsertNews(item: NewsItem) {
    upsertScopedItems(dashboardItems, dashboardQuery.value, item);
    upsertScopedItems(feedItems, feedQuery.value, item);
    upsertScopedItems(sentimentItems, sentimentQuery.value, item);
    dashboardLastLoadedAt.value = new Date().toISOString();
  }

  return {
    detailMap,
    analysisMap,
    analysisLoadingMap,
    analysisErrorMap,
    detailLoading,
    usingMock,
    dashboardItems,
    dashboardLoading,
    dashboardLastLoadedAt,
    dashboardStale,
    stale,
    dashboardQuery,
    feedItems,
    feedLoading,
    feedLastLoadedAt,
    feedStale,
    feedQuery,
    sentimentItems,
    sentimentLoading,
    sentimentLastLoadedAt,
    sentimentStale,
    sentimentQuery,
    loadDashboardNews,
    loadFeedNews,
    loadSentimentNews,
    loadDetail,
    loadAnalysis,
    analyzeNews,
    refreshNews,
    refreshDashboardNews,
    upsertNews,
  };
});
