<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import StaleBadge from '../components/common/StaleBadge.vue';
import WatchlistAddModal from '../components/watchlist/WatchlistAddModal.vue';
import WatchlistSidebar from '../components/watchlist/WatchlistSidebar.vue';
import { useRuntimeStatusStore } from '../stores/runtimeStatusStore';
import { useWatchlistStore } from '../stores/watchlistStore';
import type { WatchlistCandidate } from '../types/api';
import { getRuntimeDiagnostic } from '../utils/runtimeDiagnostics';
import { formatMarketTime } from '../utils/time';

const router = useRouter();
const runtimeStatusStore = useRuntimeStatusStore();
const watchlistStore = useWatchlistStore();
const isAddModalOpen = ref(false);
const addModalQuery = ref('');
const addModalSelectedCandidate = ref<WatchlistCandidate | null>(null);
const addModalAdvancedOpen = ref(false);
const addModalAlertThreshold = ref('');

const addModalMatches = computed(() => {
  const keyword = addModalQuery.value.trim().toLowerCase();
  if (!keyword) {
    return watchlistStore.candidates.slice(0, 8);
  }
  return watchlistStore.candidates
    .filter((candidate) =>
      [candidate.symbol, candidate.display_name, ...(candidate.aliases ?? [])].join(' ').toLowerCase().includes(keyword),
    )
    .slice(0, 8);
});

function openAddModal() {
  watchlistStore.createError = null;
  isAddModalOpen.value = true;
}

function closeAddModal() {
  watchlistStore.createError = null;
  isAddModalOpen.value = false;
  addModalQuery.value = '';
  addModalSelectedCandidate.value = null;
  addModalAdvancedOpen.value = false;
  addModalAlertThreshold.value = '';
}

function handleSelectAddCandidate(candidate: WatchlistCandidate) {
  addModalSelectedCandidate.value = candidate;
}

async function handleSelectSymbol(symbol: string) {
  await watchlistStore.selectSymbol(symbol);
  await router.push({ name: 'watchlist-detail', params: { symbol } });
}

async function handleAddCandidate() {
  if (!addModalSelectedCandidate.value) {
    return;
  }

  const threshold = addModalAlertThreshold.value.trim();
  try {
    await watchlistStore.createWatchlist({
      symbol: addModalSelectedCandidate.value.symbol,
      market: addModalSelectedCandidate.value.market,
      display_name: addModalSelectedCandidate.value.display_name,
      alert_threshold: addModalAdvancedOpen.value && threshold ? Number(threshold) : null,
      alert_mode: 'fixed',
    });
    await watchlistStore.selectSymbol(addModalSelectedCandidate.value.symbol);
    await router.push({ name: 'watchlist-detail', params: { symbol: addModalSelectedCandidate.value.symbol } });
    closeAddModal();
  } catch {
    // Keep modal state intact so the user can retry or adjust settings.
  }
}

async function handleDeleteSymbol(symbol: string) {
  if (!window.confirm(`确认删除 ${symbol} 吗？`)) {
    return;
  }
  try {
    await watchlistStore.deleteWatchlist(symbol);
  } catch {
  }
}

async function handleManualRefresh() {
  try {
    await watchlistStore.refreshMarketQuotes();
    if (watchlistStore.selectedSymbol) {
      await watchlistStore.selectSymbol(watchlistStore.selectedSymbol);
    }
  } catch {
  }
}

const runtimeDiagnostic = computed(() =>
  getRuntimeDiagnostic({
    connectionState: 'live',
    streamStatus: runtimeStatusStore.streamStatus ?? null,
    usingMock: runtimeStatusStore.usingMock ?? false,
    marketWorkerStatus: runtimeStatusStore.marketWorkerStatus,
  }),
);

onMounted(async () => {
  try {
    await watchlistStore.loadCandidates();
  } catch {
    // Candidate lookup is optional; keep the dashboard loading.
  }
  await watchlistStore.loadWatchlist();
});
</script>

<template>
  <div class="grid gap-4" data-role="watchlist-dashboard">
    <header class="flex flex-col gap-3 rounded-[24px] border border-border bg-[linear-gradient(135deg,rgba(19,27,39,0.96),rgba(10,15,24,0.98))] p-5 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Watchlist</p>
        <h1 class="page-title mb-2">自选股</h1>
        <p class="page-subtitle">搜索、添加并快速切换到单股 K 线详情。</p>
      </div>
      <StaleBadge :stale="watchlistStore.stale" label="行情列表" />
    </header>

    <section
      class="grid gap-2 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(135deg,rgba(12,19,31,0.94),rgba(8,14,24,0.98))] px-4 py-3 text-sm shadow-[0_16px_36px_rgba(2,6,12,0.22)]"
      data-role="market-worker-status"
    >
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Market Worker</span>
        <strong class="text-text">{{ runtimeStatusStore.marketWorkerStatus?.name ?? 'market_quote_producer' }}</strong>
        <span class="rounded-full border border-border px-2 py-0.5 text-[11px] uppercase tracking-[0.18em] text-text-faint">
          {{ runtimeStatusStore.marketWorkerStatus?.status ?? 'unknown' }}
        </span>
        <button
          class="rounded-full border border-[#ff9f2f33] bg-[rgba(255,159,47,0.08)] px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-[#ffca97] transition hover:bg-[rgba(255,159,47,0.14)] disabled:cursor-progress disabled:opacity-60"
          :disabled="watchlistStore.refreshLoading"
          data-role="market-refresh-action"
          @click="handleManualRefresh"
        >
          {{ watchlistStore.refreshLoading ? '刷新中...' : '立即刷新一轮' }}
        </button>
      </div>
      <p class="m-0 text-text-soft" data-role="runtime-diagnostic-headline">{{ runtimeDiagnostic.headline }}</p>
      <p class="m-0 text-text-soft" data-role="runtime-diagnostic-detail">{{ runtimeDiagnostic.detail }}</p>
      <p v-if="watchlistStore.lastManualRefreshResult" class="m-0 text-text-soft">
        最近手动刷新：{{ formatMarketTime(watchlistStore.lastManualRefreshResult.triggered_at, 'us') }}
      </p>
      <p v-if="watchlistStore.refreshError" class="m-0 text-negative">{{ watchlistStore.refreshError }}</p>
    </section>

    <section>
      <WatchlistSidebar
        :items="watchlistStore.items"
        :quotes="watchlistStore.quotes"
        :selected-symbol="watchlistStore.selectedSymbol"
        :sparklines="watchlistStore.sparklines"
        :delete-error="watchlistStore.deleteError"
        :delete-loading-symbol="watchlistStore.deleteLoadingSymbol"
        @select="handleSelectSymbol"
        @open-add-modal="openAddModal"
        @delete="handleDeleteSymbol"
        @refresh="handleManualRefresh"
      />
    </section>

    <WatchlistAddModal
      :open="isAddModalOpen"
      :query="addModalQuery"
      :matches="addModalMatches"
      :selected-candidate="addModalSelectedCandidate"
      :advanced-open="addModalAdvancedOpen"
      :alert-threshold="addModalAlertThreshold"
      :create-loading="watchlistStore.createLoading"
      :create-error="watchlistStore.createError"
      @close="closeAddModal"
      @update-query="addModalQuery = $event"
      @select-candidate="handleSelectAddCandidate"
      @toggle-advanced="addModalAdvancedOpen = !addModalAdvancedOpen"
      @update-alert-threshold="addModalAlertThreshold = $event"
      @submit="handleAddCandidate"
    />
  </div>
</template>
