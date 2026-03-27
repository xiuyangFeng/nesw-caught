<script setup lang="ts">
import { computed } from 'vue';

import type { WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import StockSparkline from './StockSparkline.vue';

const props = defineProps<{
  row: WatchlistQuoteSummary;
  selected: boolean;
  sparkline: number[];
  deleting: boolean;
}>();

defineEmits<{
  select: [symbol: string];
  delete: [symbol: string];
}>();

const toneClass = computed(() => {
  if ((props.row.change_percent ?? 0) > 0) {
    return 'text-positive';
  }
  if ((props.row.change_percent ?? 0) < 0) {
    return 'text-negative';
  }
  return 'text-text-soft';
});
</script>

<template>
  <article
    class="grid gap-2 rounded-[16px] border px-3 py-2.5 text-left transition duration-150 ease-out hover:-translate-y-px"
    :class="
      selected
        ? 'border-[#ffb66d] bg-[linear-gradient(160deg,rgba(35,23,11,0.98),rgba(18,13,10,0.98))] shadow-[0_12px_24px_rgba(255,159,47,0.14)]'
        : 'border-border bg-[linear-gradient(180deg,rgba(10,17,27,0.96),rgba(7,12,22,0.98))]'
    "
    :data-role="`stock-card-${row.symbol}`"
    data-density="compact"
    role="button"
    tabindex="0"
    @click="$emit('select', row.symbol)"
    @keydown.enter.prevent="$emit('select', row.symbol)"
    @keydown.space.prevent="$emit('select', row.symbol)"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="grid gap-0.5">
        <strong class="text-sm text-text">{{ row.display_name ?? row.symbol }}</strong>
        <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ row.symbol }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="rounded-full border border-border px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-text-faint">
          {{ row.market }}
        </span>
        <button
          type="button"
          class="rounded-full border border-[rgba(248,113,113,0.28)] px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-[#fecaca]"
          :disabled="deleting"
          @click.stop="$emit('delete', row.symbol)"
        >
          {{ deleting ? '...' : 'Del' }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
      <div class="grid gap-0.5">
        <strong class="text-lg leading-none text-text">{{ formatNumber(row.price) }}</strong>
        <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">Vol {{ formatNumber(row.volume, 0) }}</span>
      </div>
      <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold" :class="toneClass">
        {{ formatPercent(row.change_percent) }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <div class="min-w-0 flex-1">
        <StockSparkline :prices="sparkline" />
      </div>
      <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">{{ row.is_abnormal ? 'Abnormal' : 'Stable' }}</span>
    </div>
  </article>
</template>
