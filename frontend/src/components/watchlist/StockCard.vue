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
    class="grid gap-2 rounded-md border px-3 py-2 text-left transition duration-150 ease-out hover:-translate-y-px hover:border-border-strong"
    :class="
      selected
        ? 'border-accent/60 bg-accent/10'
        : 'border-border bg-panel'
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
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-danger opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-danger shadow-[0_0_8px_var(--danger)]"></span>
          </div>
          <!-- 距财报角标：数据来自 /calendar 接口，无未来财报则不显示 -->
          <span
            v-if="earningsDaysUntil !== null"
            class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold tracking-[0.06em] whitespace-nowrap"
            :class="
              earningsDaysUntil <= 3
                ? 'stock-card-earnings-near border-warning/40 bg-warning/10 text-warning'
                : 'border-system/30 bg-system/10 text-system'
            "
            :title="`距下次财报 ${earningsDaysUntil} 天`"
          >
            财报 {{ earningsDaysUntil }}天
          </span>
        </div>
        <span class="num text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ row.symbol }}</span>
        <div class="mt-0.5 flex items-end gap-2">
          <strong class="num text-[22px] leading-none text-text">{{ formatNumber(row.price) }}</strong>
          <span class="num pb-0.5 text-[10px] uppercase tracking-[0.12em] text-text-faint">Vol {{ formatNumber(row.volume, 0) }}</span>
        </div>
      </div>
      <div class="grid min-w-[78px] justify-items-end gap-1">
        <button
          type="button"
          class="inline-flex h-6 w-6 items-center justify-center rounded-full border border-danger/30 text-[10px] uppercase tracking-[0.18em] text-danger"
          :disabled="deleting"
          @click.stop="$emit('delete', row.symbol)"
        >
          {{ deleting ? '…' : '×' }}
        </button>
        <span class="num text-sm font-semibold leading-none" :class="toneClass">
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
      <span class="num text-[10px] font-medium tracking-[0.08em]" :class="toneClass">
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
    box-shadow: 0 0 0 color-mix(in srgb, var(--warning) 0%, transparent);
  }
  50% {
    box-shadow: 0 0 10px color-mix(in srgb, var(--warning) 40%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stock-card-earnings-near {
    animation: none;
  }
}
</style>
