import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { MarketWorkerStatus, StreamStatus } from '../types/api';

function isOlderThanSeconds(utcIso: string | null, thresholdSeconds: number): boolean {
  if (!utcIso) {
    return true;
  }
  const epochMs = new Date(utcIso).getTime();
  if (Number.isNaN(epochMs)) {
    return true;
  }
  return Date.now() - epochMs > thresholdSeconds * 1000;
}

export const useRuntimeStatusStore = defineStore('runtimeStatusStore', () => {
  const streamStatus = ref<StreamStatus | null>(null);
  const marketWorkerStatus = ref<MarketWorkerStatus | null>(null);
  const usingMock = ref(false);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastLoadedAt = ref<string | null>(null);

  async function loadRuntimeStatus() {
    loading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getStreamStatus();
      streamStatus.value = response.data;
      marketWorkerStatus.value = response.data.market_worker ?? null;
      usingMock.value = response.degraded;
      lastLoadedAt.value = new Date().toISOString();
    } catch {
      error.value = '运行状态加载失败，请检查后端服务';
      throw new Error(error.value);
    } finally {
      loading.value = false;
    }
  }

  async function loadRuntimeStatusIfStale(maxAgeSeconds = 15) {
    if (loading.value) {
      return;
    }
    if (!isOlderThanSeconds(lastLoadedAt.value, maxAgeSeconds)) {
      return;
    }
    await loadRuntimeStatus();
  }

  return {
    streamStatus,
    marketWorkerStatus,
    usingMock,
    loading,
    error,
    lastLoadedAt,
    loadRuntimeStatus,
    loadRuntimeStatusIfStale,
  };
});
