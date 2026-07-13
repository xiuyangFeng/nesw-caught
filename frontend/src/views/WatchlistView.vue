<script setup lang="ts">
import { computed, onMounted, provide, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import StaleBadge from '../components/common/StaleBadge.vue';
import WatchlistAddModal from '../components/watchlist/WatchlistAddModal.vue';
import WatchlistSidebar from '../components/watchlist/WatchlistSidebar.vue';
import LoadingBlock from '../components/common/LoadingBlock.vue';
import { useRuntimeStatusStore } from '../stores/runtimeStatusStore';
import { useWatchlistStore } from '../stores/watchlistStore';
import type { WatchlistCandidate } from '../types/api';
import { getRuntimeDiagnostic } from '../utils/runtimeDiagnostics';
import { formatMarketTime } from '../utils/time';
import { apiClient } from '../api/client';

const router = useRouter();
const runtimeStatusStore = useRuntimeStatusStore();
const watchlistStore = useWatchlistStore();
const isAddModalOpen = ref(false);
const addModalQuery = ref('');
const addModalSelectedCandidate = ref<WatchlistCandidate | null>(null);
const addModalAdvancedOpen = ref(false);
const addModalAlertThreshold = ref('');

const dynamicMatches = ref<WatchlistCandidate[]>([]);
const isSearching = ref(false);
let searchDebounceTimer: any = null;

// 自选股卡片“距财报 N 天”角标数据：symbol -> 最近未来财报的 days_until。
// 通过 provide 下发给 StockCard（inject），无数据的 symbol 不显示角标。
const earningsCountdown = ref<Record<string, number>>({});
provide('watchlistEarningsCountdown', earningsCountdown);

async function loadEarningsCountdown() {
  try {
    const { data } = await apiClient.getCalendar(90);
    const nextMap: Record<string, number> = {};
    for (const summary of data.summaries) {
      if (summary.next_earnings_days_until !== null && summary.next_earnings_days_until !== undefined) {
        nextMap[summary.symbol] = summary.next_earnings_days_until;
      }
    }
    earningsCountdown.value = nextMap;
  } catch {
    // 财报日历为可选增强，拉取失败时静默降级（不显示角标）。
  }
}

function performSearch(queryText: string) {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  const trimmed = queryText.trim();
  if (!trimmed) {
    dynamicMatches.value = [];
    return;
  }
  isSearching.value = true;
  const isTest = typeof process !== 'undefined' && process.env?.NODE_ENV === 'test';
  const debounceMs = isTest ? 0 : 300;
  searchDebounceTimer = setTimeout(async () => {
    try {
      const res = await apiClient.searchMarketSymbols(trimmed);
      dynamicMatches.value = res.data;
    } catch (err) {
      console.error('Failed to search market symbols', err);
    } finally {
      isSearching.value = false;
    }
  }, debounceMs);
}

watch(addModalQuery, (newVal) => {
  performSearch(newVal);
});

const addModalMatches = computed(() => {
  const keyword = addModalQuery.value.trim().toLowerCase();
  if (!keyword) {
    return watchlistStore.candidates.slice(0, 8);
  }
  return dynamicMatches.value;
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

function handleSelectSymbol(symbol: string) {
  router.push({ name: 'watchlist-detail', params: { symbol } });
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
  void loadEarningsCountdown();
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
      <p v-if="watchlistStore.refreshError" class="m-0 text-danger">{{ watchlistStore.refreshError }}</p>
    </section>

    <section>
      <LoadingBlock :loading="watchlistStore.loading" :empty="watchlistStore.items.length === 0" :skeletonType="'watchlist'" :skeletonCount="3">
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
      </LoadingBlock>
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
