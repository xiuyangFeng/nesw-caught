<script setup lang="ts">
import { computed, ref } from 'vue';

import type { WatchlistItem, WatchlistQuoteSummary } from '../../types/api';
import StockCard from './StockCard.vue';

const props = defineProps<{
  items: WatchlistItem[];
  quotes: WatchlistQuoteSummary[];
  selectedSymbol: string | null;
  sparklines: Record<string, number[]>;
  deleteError: string | null;
  deleteLoadingSymbol: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
  openAddModal: [];
  delete: [symbol: string];
  refresh: [];
}>();

const query = ref('');

const filteredRows = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  const rows = props.quotes.slice().sort((left, right) => Math.abs(right.change_percent ?? 0) - Math.abs(left.change_percent ?? 0));
  if (!keyword) {
    return rows;
  }
  return rows.filter((row) => `${row.symbol} ${row.display_name ?? ''}`.toLowerCase().includes(keyword));
});

</script>

<template>
  <aside class="grid gap-4" data-role="watchlist-sidebar">
    <div class="rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(11,18,28,0.98),rgba(8,14,23,0.98))] p-4">
      <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Watchlist Radar</p>
      <h2 class="mt-2 text-lg text-text">Trading Dashboard</h2>
      <button
        type="button"
        class="mt-4 w-full rounded-2xl border border-[#ff9f2f4f] bg-[linear-gradient(135deg,#9b5718,#ff9f2f)] px-4 py-3 text-sm font-semibold text-[#2f1500] transition hover:brightness-105"
        data-role="watchlist-open-add-modal"
        @click="emit('openAddModal')"
      >
        搜索 / 添加自选股
      </button>
      <input
        v-model.trim="query"
        class="mt-3 w-full rounded-2xl border border-border bg-field px-3 py-2.5 text-sm text-text"
        placeholder="筛选已添加股票"
      />
      <button
        type="button"
        class="mt-3 rounded-full border border-[#ff9f2f4f] bg-[linear-gradient(135deg,#9b5718,#ff9f2f)] px-4 py-2 text-sm font-semibold text-[#2f1500] disabled:opacity-60"
        data-role="watchlist-refresh-action"
        @click="emit('refresh')"
      >
        立即刷新一轮
      </button>
      <p v-if="deleteError" class="mt-2 text-sm text-negative">{{ deleteError }}</p>
    </div>

    <div class="grid gap-3">
      <StockCard
        v-for="row in filteredRows"
        :key="row.symbol"
        :row="row"
        :selected="row.symbol === selectedSymbol"
        :sparkline="sparklines[row.symbol] ?? []"
        :deleting="deleteLoadingSymbol === row.symbol"
        @select="emit('select', $event)"
        @delete="emit('delete', $event)"
      />
    </div>
  </aside>
</template>
