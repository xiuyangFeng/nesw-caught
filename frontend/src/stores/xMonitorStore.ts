import { computed, reactive, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type {
  Market,
  XAccount,
  XAccountCreatePayload,
  XAccountUpdatePayload,
  XHealth,
  XPost,
  XRefreshResult,
} from '../types/api';
import { isStale } from '../utils/time';

type TranslationStatus = 'idle' | 'loading' | 'success' | 'error';

interface TranslationState {
  status: TranslationStatus;
  translated_text: string | null;
  error: string | null;
}

export const useXMonitorStore = defineStore('xMonitorStore', () => {
  const accounts = ref<XAccount[]>([]);
  const posts = ref<XPost[]>([]);
  const health = ref<XHealth | null>(null);
  const loading = ref(false);
  const healthLoading = ref(false);
  const refreshLoading = ref(false);
  const searchLoading = ref(false);
  const accountMutationLoading = ref(false);
  const importExportLoading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const lastRefresh = ref<XRefreshResult | null>(null);
  const searchQuery = ref('');
  const searchTierFilter = ref<'core' | 'watch' | 'muted' | ''>('');
  const searchResults = ref<XPost[]>([]);
  const translationsByKey = reactive<Record<string, TranslationState>>({});
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

  function getTranslationKey(post: XPost) {
    return post.canonical_url ?? `${post.account_handle}:${post.posted_at ?? post.captured_at}:${post.content_text}`;
  }

  function getTranslationState(post: XPost): TranslationState {
    return translationsByKey[getTranslationKey(post)] ?? {
      status: 'idle',
      translated_text: null,
      error: null,
    };
  }

  function getAccountByHandle(handle: string): XAccount | null {
    return accounts.value.find((item) => item.handle === handle) ?? null;
  }

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

  async function searchPosts() {
    const q = searchQuery.value.trim();
    if (!q || (health.value && !health.value.enabled)) {
      searchResults.value = [];
      return;
    }
    searchLoading.value = true;
    const response = await apiClient.getXSearchResults({ q, limit: 20 });
    searchResults.value = response.data;
    usingMock.value = usingMock.value || response.degraded;
    searchLoading.value = false;
  }

  async function createAccount(payload: XAccountCreatePayload) {
    accountMutationLoading.value = true;
    const response = await apiClient.createXAccount(payload);
    usingMock.value = usingMock.value || response.degraded;
    accountMutationLoading.value = false;
    await loadAccounts();
  }

  async function updateAccount(handle: string, payload: XAccountUpdatePayload) {
    accountMutationLoading.value = true;
    const response = await apiClient.updateXAccount(handle, payload);
    usingMock.value = usingMock.value || response.degraded;
    accountMutationLoading.value = false;
    await loadAccounts();
  }

  async function deleteAccount(handle: string) {
    accountMutationLoading.value = true;
    const response = await apiClient.deleteXAccount(handle);
    usingMock.value = usingMock.value || response.degraded;
    accountMutationLoading.value = false;
    await Promise.all([loadAccounts(), loadPosts()]);
  }

  async function importAccounts() {
    importExportLoading.value = true;
    const response = await apiClient.importXAccounts();
    usingMock.value = usingMock.value || response.degraded;
    importExportLoading.value = false;
    await Promise.all([loadAccounts(), loadPosts()]);
    return response.data;
  }

  async function exportAccounts() {
    importExportLoading.value = true;
    const response = await apiClient.exportXAccounts();
    usingMock.value = usingMock.value || response.degraded;
    importExportLoading.value = false;
    return response.data;
  }

  async function translatePost(post: XPost) {
    const text = post.content_text.trim();
    if (!text) {
      return;
    }

    const key = getTranslationKey(post);
    const existing = translationsByKey[key];
    if (existing?.status === 'loading' || existing?.status === 'success') {
      return;
    }

    translationsByKey[key] = {
      status: 'loading',
      translated_text: existing?.translated_text ?? null,
      error: null,
    };

    try {
      const response = await apiClient.translateText({ text });
      usingMock.value = usingMock.value || response.degraded;
      translationsByKey[key] = {
        status: 'success',
        translated_text: response.data.translated_text,
        error: null,
      };
    } catch (error) {
      translationsByKey[key] = {
        status: 'error',
        translated_text: null,
        error: error instanceof Error ? error.message : '翻译失败',
      };
    }
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
    searchLoading,
    accountMutationLoading,
    importExportLoading,
    usingMock,
    lastLoadedAt,
    lastRefresh,
    searchQuery,
    searchTierFilter,
    searchResults,
    translationsByKey,
    filters,
    stale,
    getTranslationKey,
    getTranslationState,
    getAccountByHandle,
    loadHealth,
    loadAccounts,
    loadPosts,
    refreshPosts,
    searchPosts,
    createAccount,
    updateAccount,
    deleteAccount,
    importAccounts,
    exportAccounts,
    translatePost,
    bootstrap,
  };
});
