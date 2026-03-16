import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { Market, XAccount, XHealth, XPost, XRefreshResult } from '../types/api';
import { isStale } from '../utils/time';

export const useXMonitorStore = defineStore('xMonitorStore', () => {
  const accounts = ref<XAccount[]>([]);
  const posts = ref<XPost[]>([]);
  const health = ref<XHealth | null>(null);
  const loading = ref(false);
  const healthLoading = ref(false);
  const refreshLoading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const lastRefresh = ref<XRefreshResult | null>(null);
  const filters = reactive<{
    account_handle: string;
    market: Market | '';
    q: string;
  }>({
    account_handle: '',
    market: '',
    q: '',
  });

  const stale = computed(() => isStale(lastLoadedAt.value, 10));

  async function loadHealth() {
    healthLoading.value = true;
    const response = await apiClient.getXHealth();
    health.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    healthLoading.value = false;
  }

  async function loadAccounts() {
    if (health.value && !health.value.enabled) {
      accounts.value = [];
      return;
    }
    const response = await apiClient.getXAccounts();
    accounts.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
  }

  async function loadPosts() {
    if (health.value && !health.value.enabled) {
      posts.value = [];
      lastLoadedAt.value = new Date().toISOString();
      return;
    }
    loading.value = true;
    const response = await apiClient.getXPosts(filters);
    posts.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    lastLoadedAt.value = new Date().toISOString();
    loading.value = false;
  }

  async function refreshPosts() {
    if (health.value && !health.value.enabled) {
      return;
    }
    refreshLoading.value = true;
    const response = await apiClient.refreshXPosts();
    lastRefresh.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    refreshLoading.value = false;
    await Promise.all([loadHealth(), loadPosts()]);
  }

  async function bootstrap() {
    await loadHealth();
    await Promise.all([loadAccounts(), loadPosts()]);
  }

  return {
    accounts,
    posts,
    health,
    loading,
    healthLoading,
    refreshLoading,
    usingMock,
    lastLoadedAt,
    lastRefresh,
    filters,
    stale,
    loadHealth,
    loadAccounts,
    loadPosts,
    refreshPosts,
    bootstrap,
  };
});
