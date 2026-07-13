<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue';

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

// 由 WatchlistView provide 的“距财报天数”表；无 provider 时默认空表（不显示角标）。
const earningsCountdown = inject<Ref<Record<string, number>>>('watchlistEarningsCountdown', ref({}));
const earningsDaysUntil = computed<number | null>(() => {
  const value = earningsCountdown.value[props.row.symbol];
  return typeof value === 'number' ? value : null;
});

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
    class="grid gap-2 rounded-[15px] border px-3 py-2 text-left transition duration-150 ease-out hover:-translate-y-px"
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
    <div class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
      <div class="grid min-w-0 gap-1">
        <div class="flex min-w-0 items-center gap-2">
          <strong class="truncate text-[13px] font-semibold text-text">{{ row.display_name ?? row.symbol }}</strong>
          <span class="rounded-full border border-border/80 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.18em] text-text-faint">
            {{ row.market }}
          </span>
          <!-- 雷达警报灯 -->
          <div v-if="row.has_hot_alert" class="relative flex h-2 w-2 shrink-0 ml-1" title="12小时内有重大警报新闻">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-red-600 shadow-[0_0_8px_#ef4444]"></span>
          </div>
          <!-- 距财报角标：数据来自 /calendar 接口，无未来财报则不显示 -->
          <span
            v-if="earningsDaysUntil !== null"
            class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold tracking-[0.06em] whitespace-nowrap"
            :class="
              earningsDaysUntil <= 3
                ? 'stock-card-earnings-near border-[#ff9f2f66] bg-[rgba(255,159,47,0.12)] text-[#ffca97]'
                : 'border-[#53c2ff40] bg-[rgba(83,194,255,0.08)] text-[#9bd8ff]'
            "
            :title="`距下次财报 ${earningsDaysUntil} 天`"
          >
            财报 {{ earningsDaysUntil }}天
          </span>
        </div>
        <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ row.symbol }}</span>
        <div class="mt-0.5 flex items-end gap-2">
          <strong class="text-[22px] leading-none text-text">{{ formatNumber(row.price) }}</strong>
          <span class="pb-0.5 text-[10px] uppercase tracking-[0.12em] text-text-faint">Vol {{ formatNumber(row.volume, 0) }}</span>
        </div>
      </div>
      <div class="grid min-w-[78px] justify-items-end gap-1">
        <button
          type="button"
          class="inline-flex h-6 w-6 items-center justify-center rounded-full border border-[rgba(248,113,113,0.28)] text-[10px] uppercase tracking-[0.18em] text-[#fecaca]"
          :disabled="deleting"
          @click.stop="$emit('delete', row.symbol)"
        >
          {{ deleting ? '…' : '×' }}
        </button>
        <span class="text-sm font-semibold leading-none" :class="toneClass">
          {{ formatPercent(row.change_percent) }}
        </span>
        <!-- 后端 QuoteSummaryView 不含 is_abnormal 字段，改以 status 表达异常态 -->
        <span class="text-[9px] uppercase tracking-[0.18em] text-text-faint">{{ row.status === 'ok' ? 'Stable' : row.status }}</span>
      </div>
    </div>

    <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
      <div class="min-w-0 flex-1">
        <StockSparkline :prices="sparkline" />
      </div>
      <span class="text-[10px] font-medium tracking-[0.08em]" :class="toneClass">
        {{ formatNumber(row.change_amount) }}
      </span>
    </div>
  </article>
</template>

<style scoped>
/* 临近财报（≤3 天）角标呼吸高亮。 */
.stock-card-earnings-near {
  animation: stock-card-earnings-breathe 2.4s ease-in-out infinite;
}

@keyframes stock-card-earnings-breathe {
  0%,
  100% {
    box-shadow: 0 0 0 rgba(255, 159, 47, 0);
  }
  50% {
    box-shadow: 0 0 10px rgba(255, 159, 47, 0.4);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stock-card-earnings-near {
    animation: none;
  }
}
</style>
