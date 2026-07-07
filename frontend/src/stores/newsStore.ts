import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { NewsAnalysis, NewsDetail, NewsFeedLayout, NewsItem, NewsQuery, NewsRuntimeSource, NewsRuntimeStatus, NewsUpdateEvent } from '../types/api';
import { isStale } from '../utils/time';

export const useNewsStore = defineStore('newsStore', () => {
  const detailMap = ref<Record<number, NewsDetail | null>>({});
  const analysisMap = ref<Record<number, NewsAnalysis | null>>({});
  const analysisLoadingMap = ref<Record<number, boolean>>({});
  const analysisErrorMap = ref<Record<number, string | null>>({});
  const detailLoading = ref(false);
  const usingMock = ref(false);
  const newsRuntimeStatus = ref<NewsRuntimeStatus | null>(null);
  const lastIncrementalAt = ref<string | null>(null);
  const sourceHealth = ref<NewsRuntimeSource[]>([]);

  const dashboardItems = ref<NewsItem[]>([]);
  const dashboardLoading = ref(false);
  const dashboardLastLoadedAt = ref<string | null>(null);
  const dashboardQuery = ref<NewsQuery>({ limit: 50 });
  const dashboardRequestId = ref(0);

  const feedItems = ref<NewsItem[]>([]);
  const feedLoading = ref(false);
  const feedLoadingMore = ref(false);
  const feedNextCursor = ref<string | null>(null);
  const feedHasMore = computed(() => feedNextCursor.value !== null);
  const feedPendingRequests = ref(0);
  const feedNewsRequestId = ref(0);
  const feedLayoutRequestId = ref(0);
  const feedLastLoadedAt = ref<string | null>(null);
  const feedQuery = ref<NewsQuery>({ limit: 50 });
  const feedLayout = ref<NewsFeedLayout>({
    events: [],
    topics: [],
    stream: [],
  });
  const feedLayoutDegraded = ref(false);
  const feedLayoutStreamLimit = ref<number | null>(null);

  const sentimentItems = ref<NewsItem[]>([]);
  const sentimentLoading = ref(false);
  const sentimentLastLoadedAt = ref<string | null>(null);
  const sentimentQuery = ref<NewsQuery>({ limit: 50 });
  const sentimentRequestId = ref(0);

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
      requestId: typeof dashboardRequestId;
    },
  ) {
    const requestId = ++options.requestId.value;
    options.loading.value = true;
    options.queryRef.value = { ...query };
    try {
      const response = await apiClient.getNews(options.queryRef.value);
      if (requestId === options.requestId.value) {
        options.items.value = response.data.items;
        usingMock.value = usingMock.value || response.degraded;
        options.lastLoadedAt.value = new Date().toISOString();
      }
    } finally {
      if (requestId === options.requestId.value) {
        options.loading.value = false;
      }
    }
  }

  async function loadDashboardNews(query: NewsQuery = dashboardQuery.value) {
    await loadScopedNews(query, {
      items: dashboardItems,
      loading: dashboardLoading,
      lastLoadedAt: dashboardLastLoadedAt,
      queryRef: dashboardQuery,
      requestId: dashboardRequestId,
    });
  }

  async function loadFeedNews(query: NewsQuery = feedQuery.value) {
    feedPendingRequests.value += 1;
    feedLoading.value = true;
    const requestId = ++feedNewsRequestId.value;
    try {
      feedQuery.value = { ...query };
      const response = await apiClient.getNews(feedQuery.value);
      if (requestId === feedNewsRequestId.value) {
        feedItems.value = response.data.items;
        feedNextCursor.value = response.data.next_cursor ?? null;
        usingMock.value = usingMock.value || response.degraded;
        feedLastLoadedAt.value = new Date().toISOString();
      }
    } finally {
      feedPendingRequests.value = Math.max(0, feedPendingRequests.value - 1);
      feedLoading.value = feedPendingRequests.value > 0;
    }
  }

  async function loadMoreFeedNews() {
    if (!feedNextCursor.value || feedLoadingMore.value || feedLoading.value) {
      return false;
    }
    feedLoadingMore.value = true;
    const requestId = ++feedNewsRequestId.value;
    try {
      const response = await apiClient.getNews({
        ...feedQuery.value,
        cursor: feedNextCursor.value,
      });
      if (requestId !== feedNewsRequestId.value) {
        return false;
      }
      const existingIds = new Set(feedItems.value.map((item) => item.id));
      const appended = response.data.items.filter((item) => !existingIds.has(item.id));
      feedItems.value = [...feedItems.value, ...appended];
      feedNextCursor.value = response.data.next_cursor ?? null;
      usingMock.value = usingMock.value || response.degraded;
      feedLastLoadedAt.value = new Date().toISOString();
      return appended.length > 0;
    } finally {
      feedLoadingMore.value = false;
    }
  }

  async function loadFeedLayout(query: { market?: string; limit_events?: number; limit_topics?: number; limit_stream?: number } = {}) {
    feedPendingRequests.value += 1;
    feedLoading.value = true;
    const requestId = ++feedLayoutRequestId.value;
    feedLayoutStreamLimit.value = query.limit_stream ?? feedLayoutStreamLimit.value;
    try {
      const response = await apiClient.getNewsFeedLayout(query);
      if (requestId === feedLayoutRequestId.value) {
        feedLayout.value = response.data;
        feedLayoutDegraded.value = response.degraded;
        usingMock.value = usingMock.value || response.degraded;
        feedLastLoadedAt.value = new Date().toISOString();
      }
    } finally {
      feedPendingRequests.value = Math.max(0, feedPendingRequests.value - 1);
      feedLoading.value = feedPendingRequests.value > 0;
    }
  }

  async function loadSentimentNews(query: NewsQuery = sentimentQuery.value) {
    await loadScopedNews(query, {
      items: sentimentItems,
      loading: sentimentLoading,
      lastLoadedAt: sentimentLastLoadedAt,
      queryRef: sentimentQuery,
      requestId: sentimentRequestId,
    });
  }

  async function loadNewsRuntime() {
    const response = await apiClient.getNewsRuntime();
    newsRuntimeStatus.value = response.data;
    lastIncrementalAt.value = response.data.last_incremental_event_at ?? null;
    sourceHealth.value = response.data.sources;
    usingMock.value = usingMock.value || response.degraded;
  }

  function upsertScopedItems(itemsRef: typeof dashboardItems, query: NewsQuery, item: NewsItem) {
    if (!matchesQuery(item, query)) {
      return;
    }

    const existingIndex = itemsRef.value.findIndex((candidate) => candidate.id === item.id);
    if (existingIndex >= 0) {
      itemsRef.value.splice(existingIndex, 1, item);
    } else {
      insertScopedItem(itemsRef, query, item);
    }
  }

  function insertScopedItem(itemsRef: typeof dashboardItems, query: NewsQuery, item: NewsItem) {
    // Pagination (loadMoreFeedNews) can grow the list far beyond query.limit,
    // so the cap must never shrink the list back to the base page size.
    const maxLength = Math.max(query.limit ?? 0, itemsRef.value.length);
    itemsRef.value.unshift(item);
    if (maxLength > 0 && itemsRef.value.length > maxLength) {
      itemsRef.value.length = maxLength;
    }
  }

  function upsertScopedUpdate(itemsRef: typeof dashboardItems, query: NewsQuery, item: NewsItem) {
    const existingIndex = itemsRef.value.findIndex((candidate) => candidate.id === item.id);
    if (!matchesQuery(item, query)) {
      if (existingIndex >= 0) {
        itemsRef.value.splice(existingIndex, 1);
      }
      return;
    }

    if (existingIndex >= 0) {
      itemsRef.value.splice(existingIndex, 1, item);
    } else {
      insertScopedItem(itemsRef, query, item);
    }
  }

  function upsertLayoutStream(item: NewsItem) {
    const nextStream = [...feedLayout.value.stream];
    const existingIndex = nextStream.findIndex((candidate) => candidate.id === item.id);
    if (existingIndex >= 0) {
      nextStream.splice(existingIndex, 1, item);
    } else {
      // Cap by the layout stream limit (not the raw feed query limit), and
      // never shrink below what has already been loaded.
      const maxLength = Math.max(feedLayoutStreamLimit.value ?? 0, nextStream.length);
      nextStream.unshift(item);
      if (maxLength > 0 && nextStream.length > maxLength) {
        nextStream.length = maxLength;
      }
    }
    feedLayout.value = {
      ...feedLayout.value,
      stream: nextStream,
    };
  }

  async function loadDetail(id: number) {
    detailLoading.value = true;
    try {
      const response = await apiClient.getNewsDetail(id);
      detailMap.value[id] = response.data;
      usingMock.value = usingMock.value || response.degraded;
    } finally {
      detailLoading.value = false;
    }
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
    try {
      const response = await apiClient.refreshNews();
      usingMock.value = usingMock.value || response.degraded;
      if (response.degraded) {
        return false;
      }

      await loadDashboardNews(dashboardQuery.value);
      return true;
    } catch {
      // Refresh is a background convenience; callers only need success/failure.
      return false;
    }
  }

  function upsertNews(item: NewsItem) {
    upsertScopedItems(dashboardItems, dashboardQuery.value, item);
    upsertScopedItems(feedItems, feedQuery.value, item);
    upsertScopedItems(sentimentItems, sentimentQuery.value, item);
    upsertLayoutStream(item);
    dashboardLastLoadedAt.value = new Date().toISOString();
    feedLastLoadedAt.value = new Date().toISOString();
  }

  function upsertNewsUpdate(item: NewsUpdateEvent) {
    upsertScopedUpdate(dashboardItems, dashboardQuery.value, item);
    upsertScopedUpdate(feedItems, feedQuery.value, item);
    upsertScopedUpdate(sentimentItems, sentimentQuery.value, item);
    upsertLayoutStream(item);
    feedLastLoadedAt.value = new Date().toISOString();
  }

  return {
    detailMap,
    analysisMap,
    analysisLoadingMap,
    analysisErrorMap,
    detailLoading,
    usingMock,
    newsRuntimeStatus,
    lastIncrementalAt,
    sourceHealth,
    dashboardItems,
    dashboardLoading,
    dashboardLastLoadedAt,
    dashboardStale,
    stale,
    dashboardQuery,
    feedItems,
    feedLayout,
    feedLayoutDegraded,
    feedLayoutStreamLimit,
    feedLoading,
    feedLoadingMore,
    feedHasMore,
    feedNextCursor,
    feedLastLoadedAt,
    feedStale,
    feedQuery,
    loadFeedLayout,
    loadMoreFeedNews,
    sentimentItems,
    sentimentLoading,
    sentimentLastLoadedAt,
    sentimentStale,
    sentimentQuery,
    loadDashboardNews,
    loadFeedNews,
    loadSentimentNews,
    loadNewsRuntime,
    loadDetail,
    loadAnalysis,
    analyzeNews,
    refreshNews,
    refreshDashboardNews,
    upsertNews,
    upsertNewsUpdate,
  };
});
