import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { QuantDataStatus, QuantProposal, QuantRadar, QuantRecommendationLatest } from '../types/api';

const emptyLatest: QuantRecommendationLatest = {
  available: true,
  run: null,
  items: [],
  empty_reason: 'no_run_yet',
  empty_reason_detail: '尚未运行机会流水线。手动重跑将使用合成夹具，现金为合法结果。',
};

const emptyProposal: QuantProposal = {
  cash_weight: 1,
  items: [],
  note: '无合格机会时现金为 100%。LLM 不参与权重。',
};

export const useDeskStore = defineStore('deskStore', () => {
  const latest = ref<QuantRecommendationLatest>(emptyLatest);
  const dataStatus = ref<QuantDataStatus | null>(null);
  const radar = ref<QuantRadar | null>(null);
  const proposal = ref<QuantProposal>(emptyProposal);
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
  const sleeveCounts = computed(() => {
    const counts: Record<string, { qualified: number; watch: number; total: number }> = {
      event_catalyst: { qualified: 0, watch: 0, total: 0 },
      trend_flow: { qualified: 0, watch: 0, total: 0 },
      fundamental_revalue: { qualified: 0, watch: 0, total: 0 },
    };
    for (const item of latest.value.items ?? []) {
      const bucket = counts[item.sleeve] ?? { qualified: 0, watch: 0, total: 0 };
      bucket.total += 1;
      if (item.state === 'qualified') bucket.qualified += 1;
      if (item.state === 'watch') bucket.watch += 1;
      counts[item.sleeve] = bucket;
    }
    return counts;
  });

  async function loadDesk() {
    loading.value = true;
    error.value = null;
    try {
      const [latestRes, statusRes, radarRes, proposalRes] = await Promise.all([
        apiClient.getQuantLatest(),
        apiClient.getQuantDataStatus(),
        apiClient.getQuantRadar(),
        apiClient.getQuantProposal(),
      ]);
      latest.value = latestRes.data ?? emptyLatest;
      dataStatus.value = statusRes.data;
      radar.value = radarRes.data;
      proposal.value = proposalRes.data ?? emptyProposal;
      usingMock.value = latestRes.degraded || statusRes.degraded || radarRes.degraded || proposalRes.degraded;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '交易台加载失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function rerun(scenario: 'real' | 'abstain' | 'mixed' = 'real') {
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
    proposal,
    loading,
    running,
    error,
    usingMock,
    qualifiedItems,
    watchItems,
    isDegraded,
    hasQualified,
    sleeveCounts,
    loadDesk,
    rerun,
  };
});
