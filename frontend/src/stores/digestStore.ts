import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { Digest } from '../types/api';

export const useDigestStore = defineStore('digestStore', () => {
  const digest = ref<Digest | null>(null);
  const available = ref(false);
  const loading = ref(false);
  const generating = ref(false);
  const error = ref<string | null>(null);
  const marketScope = ref<'all' | 'hk' | 'us'>('all');

  async function loadLatest() {
    loading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getLatestDigest();
      available.value = response.data.available;
      digest.value = response.data.digest ?? null;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载简报失败';
    } finally {
      loading.value = false;
    }
  }

  async function generate() {
    generating.value = true;
    error.value = null;
    try {
      const response = await apiClient.generateDigest(marketScope.value);
      digest.value = response.data;
      available.value = true;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成简报失败';
      throw err;
    } finally {
      generating.value = false;
    }
  }

  return {
    digest,
    available,
    loading,
    generating,
    error,
    marketScope,
    loadLatest,
    generate,
  };
});
