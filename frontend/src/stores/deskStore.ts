import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { QuantDataStatus, QuantRadar, QuantRecommendationLatest } from '../types/api';

const emptyLatest: QuantRecommendationLatest = {
  available: true,
  run: null,
  items: [],
  empty_reason: 'no_run_yet',
  empty_reason_detail: '尚未运行机会流水线。手动重跑将使用合成夹具，现金为合法结果。',
};

export const useDeskStore = defineStore('deskStore', () => {
  const latest = ref<QuantRecommendationLatest>(emptyLatest);
  const dataStatus = ref<QuantDataStatus | null>(null);
  const radar = ref<QuantRadar | null>(null);
  const loading = ref(false);
  const running = ref(false);
  const error = ref<string | null>(null);
  const usingMock = ref(false);

  const qualifiedItems = computed(
    () => (latest.value.items ?? []).filter((item) => item.state === 'qualified'),
  );
  const watchItems = computed(() => (latest.value.items ?? []).filter((item) => item.state === 'watch'));
  const isDegraded = computed(() => latest.value.run?.status === 'degraded' || usingMock.value);
  const hasQualified = computed(() => qualifiedItems.value.length > 0);

  async function loadDesk() {
    loading.value = true;
    error.value = null;
    try {
      const [latestRes, statusRes, radarRes] = await Promise.all([
        apiClient.getQuantLatest(),
        apiClient.getQuantDataStatus(),
        apiClient.getQuantRadar(),
      ]);
      latest.value = latestRes.data ?? emptyLatest;
      dataStatus.value = statusRes.data;
      radar.value = radarRes.data;
      usingMock.value = latestRes.degraded || statusRes.degraded || radarRes.degraded;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '交易台加载失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function rerun(scenario: 'abstain' | 'mixed' = 'abstain') {
    running.value = true;
    error.value = null;
    try {
      const response = await apiClient.runQuantRecommendations(scenario);
      latest.value = response.data ?? emptyLatest;
      await loadDesk();
    } catch (err) {
      error.value = err instanceof Error ? err.message : '重跑失败';
      throw err;
    } finally {
      running.value = false;
    }
  }

  return {
    latest,
    dataStatus,
    radar,
    loading,
    running,
    error,
    usingMock,
    qualifiedItems,
    watchItems,
    isDegraded,
    hasQualified,
    loadDesk,
    rerun,
  };
});
