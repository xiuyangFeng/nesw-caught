<script setup lang="ts">
import type { KlineDrawingTool, WatchlistDashboardPeriod } from '../../types/api';

defineProps<{
  currentPeriod: WatchlistDashboardPeriod;
  activeTool: KlineDrawingTool;
  drawingDisabled?: boolean;
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  periodChange: [period: WatchlistDashboardPeriod];
  toolChange: [tool: KlineDrawingTool];
  clearDrawings: [];
  toggleDashboard: [];
}>();

const periods: Array<{ value: WatchlistDashboardPeriod; label: string }> = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
  { value: '1Y', label: '年K' },
];

const tools: Array<{ value: KlineDrawingTool; label: string }> = [
  { value: 'select', label: '选择' },
  { value: 'trend_line', label: '趋势线' },
  { value: 'horizontal_line', label: '水平线' },
  { value: 'price_range', label: '矩形区间' },
  { value: 'fibonacci_retracement', label: '斐波那契' },
  { value: 'price_note', label: '价格标注' },
];
</script>

<template>
  <div class="grid gap-2 rounded-[16px] border border-border/70 bg-[linear-gradient(180deg,rgba(16,22,33,0.95),rgba(10,15,24,0.92))] px-3 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]" data-role="kline-toolbar-shell">
    <div class="flex flex-wrap items-center justify-between gap-2" data-role="kline-period-toolbar">
      <div class="flex flex-wrap gap-2" data-role="kline-toolbar-period-group">
        <button
          v-for="period in periods"
          :key="period.value"
          type="button"
          class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
          :class="currentPeriod === period.value ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
          :data-role="`period-chip-${period.value}`"
          :data-active="currentPeriod === period.value ? 'true' : 'false'"
          @click="emit('periodChange', period.value)"
        >
          {{ period.label }}
        </button>
      </div>
      <div class="flex flex-wrap items-center gap-2" data-role="kline-toolbar-action-group">
        <button
          type="button"
          class="rounded-full border border-[rgba(255,111,134,0.35)] px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-[#ff9dad]"
          data-role="clear-drawings"
          :disabled="drawingDisabled"
          @click="emit('clearDrawings')"
        >
          清空画线
        </button>
        <button
          type="button"
          class="rounded-full border border-border/70 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-faint"
          data-role="toggle-dashboard"
          @click="emit('toggleDashboard')"
        >
          {{ collapsed ? '展开面板' : '收起面板' }}
        </button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2" data-role="kline-toolbar-tool-group">
      <button
        v-for="tool in tools"
        :key="tool.value"
        type="button"
        class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
        :class="activeTool === tool.value ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
        :data-role="`tool-chip-${tool.value}`"
        :data-active="activeTool === tool.value ? 'true' : 'false'"
        :disabled="drawingDisabled && tool.value !== 'select'"
        @click="emit('toolChange', tool.value)"
      >
        {{ tool.label }}
      </button>
    </div>
  </div>
</template>
