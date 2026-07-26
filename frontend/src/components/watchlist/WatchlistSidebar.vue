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
    <div class="rounded-lg border border-border bg-panel p-4" data-role="watchlist-toolbar">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <p class="text-[10px] uppercase tracking-[0.22em] text-accent">Watchlist</p>
            <span class="rounded-full bg-positive/10 border border-positive/30 px-2 py-0.5 text-[9px] font-semibold text-positive">
              同花顺极速行情
            </span>
          </div>
          <h2 class="mt-1 text-base text-text">自选股列表</h2>
          <p class="text-[11px] text-text-faint mt-0.5">高密度直展股价与涨跌额包囊 · 点击标的看专业 K 线</p>
        </div>
        <button
          type="button"
          class="rounded-full bg-accent px-3.5 py-1.5 text-xs font-semibold text-[var(--bg)] transition hover:brightness-110"
          data-role="watchlist-open-add-modal"
          @click="emit('openAddModal')"
        >
          添加
        </button>
      </div>
      <div class="mt-3 flex items-center gap-2">
        <input
          v-model.trim="query"
          class="min-w-0 flex-1 rounded-xl border border-border bg-field px-3 py-2 text-sm text-text"
          placeholder="搜索已添加股票代码/名称"
        />
        <button
          type="button"
          class="shrink-0 rounded-full border border-accent/40 bg-accent/10 px-3 py-2 text-[11px] font-semibold text-accent transition hover:bg-accent/20 disabled:opacity-60"
          data-role="watchlist-refresh-action"
          @click="emit('refresh')"
        >
          刷新
        </button>
      </div>
      <p v-if="deleteError" class="mt-2 text-sm text-danger">{{ deleteError }}</p>
    </div>

    <div class="grid gap-2.5" data-role="watchlist-compact-list">
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
