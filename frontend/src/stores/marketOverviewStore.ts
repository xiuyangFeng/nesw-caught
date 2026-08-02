import { ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type {
  MarketIndexConfig,
  MarketIndexConfigCreate,
  MarketIndexConfigUpdate,
  MarketOverview,
} from '../types/api';

// 对齐 marketStore 的轮询思路：overview 数据低频（60s）定时刷新即可。
const AUTO_REFRESH_INTERVAL_MS = 60_000;

export const useMarketOverviewStore = defineStore('marketOverviewStore', () => {
  const overview = ref<MarketOverview | null>(null);
  const indexConfigs = ref<MarketIndexConfig[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);
  const configSaving = ref(false);
  const configError = ref<string | null>(null);

  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  // 注意:与 marketStore.loadSnapshots 不同,这里不把异常 rethrow 给调用方。
  // 该 action 会被 setInterval 驱动, rethrow 会变成未处理的 promise rejection;
  // 失败一律收敛进 error 状态由 UI 展示。
  async function loadOverview() {
    loading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getMarketOverview();
      overview.value = response.data;
      usingMock.value = response.degraded;
      lastLoadedAt.value = new Date().toISOString();
    } catch (err) {
      error.value = err instanceof Error ? err.message : '市场总览加载失败';
    } finally {
      loading.value = false;
    }
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    refreshTimer = setInterval(() => {
      void loadOverview();
    }, AUTO_REFRESH_INTERVAL_MS);
  }

  function stopAutoRefresh() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  async function loadIndexConfig() {
    try {
      const response = await apiClient.getMarketIndexConfig();
      indexConfigs.value = response.data;
      configError.value = null;
    } catch (err) {
      configError.value = err instanceof Error ? err.message : '指数配置加载失败';
    }
  }

  async function refreshAfterConfigChange() {
    await loadIndexConfig();
    await loadOverview();
  }

  // 配置 CRUD 成功后会自动触发 overview + 配置列表刷新;失败时 rethrow
  // 给弹窗调用方(由弹窗决定保持打开并展示 configError)。
  async function createIndexConfig(payload: MarketIndexConfigCreate) {
    configSaving.value = true;
    configError.value = null;
    try {
      await apiClient.createMarketIndexConfig(payload);
      await refreshAfterConfigChange();
    } catch (err) {
      configError.value = err instanceof Error ? err.message : '新增指数配置失败';
      throw err;
    } finally {
      configSaving.value = false;
    }
  }

  async function updateIndexConfig(id: number, payload: MarketIndexConfigUpdate) {
    configSaving.value = true;
    configError.value = null;
    try {
      await apiClient.updateMarketIndexConfig(id, payload);
      await refreshAfterConfigChange();
    } catch (err) {
      configError.value = err instanceof Error ? err.message : '更新指数配置失败';
      throw err;
    } finally {
      configSaving.value = false;
    }
  }

  async function deleteIndexConfig(id: number) {
    configSaving.value = true;
    configError.value = null;
    try {
      await apiClient.deleteMarketIndexConfig(id);
      await refreshAfterConfigChange();
    } catch (err) {
      configError.value = err instanceof Error ? err.message : '删除指数配置失败';
      throw err;
    } finally {
      configSaving.value = false;
    }
  }

  return {
    overview,
    indexConfigs,
    loading,
    error,
    usingMock,
    lastLoadedAt,
    configSaving,
    configError,
    loadOverview,
    startAutoRefresh,
    stopAutoRefresh,
    loadIndexConfig,
    createIndexConfig,
    updateIndexConfig,
    deleteIndexConfig,
  };
});
