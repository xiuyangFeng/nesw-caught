<script setup lang="ts">
import type { KlineDrawingTool, WatchlistDashboardPeriod } from '../../types/api';

defineProps<{
  currentPeriod: WatchlistDashboardPeriod;
  activeTool: KlineDrawingTool;
  drawingDisabled?: boolean;
  collapsed?: boolean;
  canUndo?: boolean;
  canRedo?: boolean;
}>();

const emit = defineEmits<{
  periodChange: [period: WatchlistDashboardPeriod];
  toolChange: [tool: KlineDrawingTool];
  clearDrawings: [];
  undo: [];
  redo: [];
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
  <div class="grid gap-2 rounded-lg border border-border bg-panel-strong px-3 py-2.5" data-role="kline-toolbar-shell">
    <div class="flex flex-wrap items-center justify-between gap-2" data-role="kline-period-toolbar">
      <div class="flex flex-wrap gap-2" data-role="kline-toolbar-period-group">
        <button
          v-for="period in periods"
          :key="period.value"
          type="button"
          class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
          :class="currentPeriod === period.value ? 'border-accent/60 bg-accent/10 text-accent' : 'border-border/70 text-text-faint'"
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
          class="rounded-full border border-border/70 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-faint disabled:cursor-not-allowed disabled:opacity-40"
          data-role="undo-action"
          :disabled="!canUndo"
          @click="emit('undo')"
        >
          撤销
        </button>
        <button
          type="button"
          class="rounded-full border border-border/70 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-faint disabled:cursor-not-allowed disabled:opacity-40"
          data-role="redo-action"
          :disabled="!canRedo"
          @click="emit('redo')"
        >
          重做
        </button>
        <button
          type="button"
          class="rounded-full border border-danger/40 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-danger disabled:cursor-not-allowed disabled:opacity-40"
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
        class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em] disabled:cursor-not-allowed disabled:opacity-40"
        :class="activeTool === tool.value ? 'border-accent/60 bg-accent/10 text-accent' : 'border-border/70 text-text-faint'"
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
