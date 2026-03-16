import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { MarketSnapshot } from '../types/api';
import { isStale } from '../utils/time';

export const useMarketStore = defineStore('marketStore', () => {
  const snapshots = ref<MarketSnapshot[]>([]);
  const loading = ref(false);
  const usingMock = ref(false);
  const lastLoadedAt = ref<string | null>(null);

  const abnormalMovers = computed(() => snapshots.value.filter((snapshot) => snapshot.is_abnormal));
  const stale = computed(() => isStale(lastLoadedAt.value, 3));

  async function loadSnapshots() {
    loading.value = true;
    const response = await apiClient.getMarketSnapshots();
    snapshots.value = response.data;
    usingMock.value = response.degraded;
    lastLoadedAt.value = new Date().toISOString();
    loading.value = false;
  }

  function upsertSnapshot(snapshot: MarketSnapshot) {
    const index = snapshots.value.findIndex((candidate) => candidate.symbol === snapshot.symbol);
    if (index >= 0) {
      snapshots.value.splice(index, 1, snapshot);
    } else {
      snapshots.value.unshift(snapshot);
    }
    lastLoadedAt.value = new Date().toISOString();
  }

  return {
    snapshots,
    loading,
    usingMock,
    lastLoadedAt,
    abnormalMovers,
    stale,
    loadSnapshots,
    upsertSnapshot,
  };
});
