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
    class="relative grid min-h-[56px] cursor-pointer grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-3.5 rounded-xl border px-3.5 py-2.5 text-left transition duration-150 ease-out hover:border-accent/50 hover:bg-white/[0.03]"
    :class="
      selected
        ? 'border-accent/70 bg-accent/10 shadow-[0_0_12px_rgba(59,130,246,0.1)]'
        : 'border-border/80 bg-panel'
    "
    :data-role="`stock-card-${row.symbol}`"
    data-density="compact"
    role="button"
    tabindex="0"
    @click="$emit('select', row.symbol)"
    @keydown.enter.prevent="$emit('select', row.symbol)"
    @keydown.space.prevent="$emit('select', row.symbol)"
  >
    <!-- 左侧：名称 / 代码 / 市场标 / 财报预警 -->
    <div class="grid min-w-0 gap-0.5">
      <div class="flex items-center gap-1.5 min-w-0">
        <strong class="truncate text-sm font-bold text-text leading-tight">{{ row.display_name ?? row.symbol }}</strong>
        <span class="shrink-0 rounded-md bg-white/10 px-1 py-0.2 text-[9px] uppercase font-semibold tracking-wider text-text-faint">
          {{ row.market }}
        </span>
        <!-- 雷达警报灯 -->
        <div v-if="row.has_hot_alert" class="relative flex h-2 w-2 shrink-0" title="12小时内有重大警报新闻">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-danger opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-danger shadow-[0_0_8px_var(--danger)]"></span>
        </div>
        <!-- 距财报角标 -->
        <span
          v-if="earningsDaysUntil !== null"
          class="shrink-0 rounded-full border px-1.5 py-0.2 text-[9px] font-semibold whitespace-nowrap"
          :class="
            earningsDaysUntil <= 3
              ? 'stock-card-earnings-near border-warning/40 bg-warning/10 text-warning'
              : 'border-accent/30 bg-accent/10 text-accent'
          "
          :title="`距下次财报 ${earningsDaysUntil} 天`"
        >
          财报 {{ earningsDaysUntil }}天
        </span>
      </div>
      <div class="flex items-center gap-2 text-[11px] text-text-faint font-mono">
        <span>{{ row.symbol }}</span>
        <span>·</span>
        <span>Vol {{ formatNumber(row.volume, 0) }}</span>
      </div>
    </div>

    <!-- 中间：当前最新股价 (随涨跌标红/标绿) -->
    <div class="grid justify-items-end text-right">
      <strong class="num font-mono text-lg font-extrabold tabular-nums tracking-tight" :class="toneClass">
        {{ formatNumber(row.price) }}
      </strong>
      <span class="text-[10px] text-text-faint uppercase font-medium">
        {{ row.status === 'ok' ? '实时行情' : row.status }}
      </span>
    </div>

    <!-- 右侧：同花顺标志高对比度涨跌幅包囊块与绝对额 -->
    <div class="grid justify-items-end gap-0.5 text-right">
      <div
        class="inline-flex min-w-[76px] items-center justify-center rounded-md px-2 py-1 text-xs font-bold font-mono leading-none tracking-tight shadow-sm"
        :class="
          (row.change_percent ?? 0) > 0
            ? 'bg-[var(--positive)] text-white shadow-[0_2px_8px_color-mix(in_srgb,var(--positive)_30%,transparent)]'
            : (row.change_percent ?? 0) < 0
              ? 'bg-[var(--negative)] text-white shadow-[0_2px_8px_color-mix(in_srgb,var(--negative)_30%,transparent)]'
              : 'bg-white/10 text-text-faint'
        "
      >
        {{ formatPercent(row.change_percent) }}
      </div>
      <span
        class="num font-mono text-[11px] font-semibold tabular-nums"
        :class="toneClass"
      >
        {{ (row.change_amount ?? 0) > 0 ? '+' : '' }}{{ formatNumber(row.change_amount) }}
      </span>
    </div>

    <!-- 最右侧：快捷删除按钮 -->
    <button
      type="button"
      class="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-faint opacity-50 transition hover:bg-danger/20 hover:text-danger hover:opacity-100"
      :disabled="deleting"
      title="从自选列表中移除"
      @click.stop="$emit('delete', row.symbol)"
    >
      {{ deleting ? '…' : '×' }}
    </button>
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
