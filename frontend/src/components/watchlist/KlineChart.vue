<script setup lang="ts">
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type {
  KlineDrawing,
  KlineDrawingStyle,
  KlineSubIndicator,
  NewsEventMarker,
  StockKlineResponse,
  WatchlistDashboardPeriod,
} from '../../types/api';
import { useWatchlistChartStore } from '../../stores/watchlistChartStore';
import { buildOverlayLines, calculateRsi } from '../../utils/klineIndicators';
import { formatNumber, formatPercent } from '../../utils/format';
import KlineDrawingOverlay from './KlineDrawingOverlay.vue';
import KlineDrawingSelectionPopover from './KlineDrawingSelectionPopover.vue';
import KlineIndicatorWorkbench from './KlineIndicatorWorkbench.vue';
import KlineToolbar from './KlineToolbar.vue';

const props = defineProps<{
  klineData: StockKlineResponse | null;
  currentPeriod?: WatchlistDashboardPeriod;
  highlightedEventTime?: string | null;
}>();

const emit = defineEmits<{
  focusNews: [event: NewsEventMarker];
  switchPeriod: [period: WatchlistDashboardPeriod];
}>();

const chartStore = useWatchlistChartStore();
const mainChartRef = ref<HTMLElement | null>(null);
const subChartRef = ref<HTMLElement | null>(null);
const dashboardCollapsed = ref(false);

let chart: IChartApi | null = null;
let subChart: IChartApi | null = null;
let candleSeries: ISeriesApi<'Candlestick'> | null = null;
let volumeSeries: ISeriesApi<'Histogram'> | null = null;
let macdHistogramSeries: ISeriesApi<'Histogram'> | null = null;
let macdDifSeries: ISeriesApi<'Line'> | null = null;
let macdDeaSeries: ISeriesApi<'Line'> | null = null;
let kSeries: ISeriesApi<'Line'> | null = null;
let dSeries: ISeriesApi<'Line'> | null = null;
let jSeries: ISeriesApi<'Line'> | null = null;
let rsiSeries: ISeriesApi<'Line'> | null = null;
const lineSeriesMap = new Map<string, ISeriesApi<'Line'>>();

const candles = computed(() => props.klineData?.candles ?? []);
const activeTemplate = computed(() => chartStore.activeTemplate);
const activeLines = computed(() => (activeTemplate.value ? buildOverlayLines(activeTemplate.value, candles.value) : []));
const activeSubIndicator = computed<KlineSubIndicator>(() => chartStore.subIndicator);
const drawings = computed(() => {
  const symbol = props.klineData?.symbol;
  return symbol ? chartStore.drawingsBySymbol[symbol] ?? [] : [];
});
const hoveredAnchor = ref<{ time: string; price: number } | null>(null);
const selectedDrawing = computed(() => {
  const symbol = props.klineData?.symbol;
  const id = chartStore.selectedDrawingId;
  return symbol && id ? chartStore.findDrawing(symbol, id) : null;
});
const selectedDrawings = computed(() => {
  const symbol = props.klineData?.symbol;
  if (!symbol) {
    return [];
  }
  return chartStore.selectedDrawingIds.map((id) => chartStore.findDrawing(symbol, id)).filter((drawing): drawing is KlineDrawing => drawing !== null);
});
const overlayDisabled = computed(() => !props.klineData || !candles.value.length);
const labelEditingActive = ref(false);
const chartProjector = computed(() => ({
  getXForTime(time: string) {
    return (chart?.timeScale() as { timeToCoordinate?: (value: string) => number | null } | undefined)?.timeToCoordinate?.(time) ?? null;
  },
  getTimeForX(x: number) {
    return (chart?.timeScale() as { coordinateToTime?: (value: number) => string | null } | undefined)?.coordinateToTime?.(x) ?? null;
  },
  getYForPrice(price: number) {
    return (candleSeries as { priceToCoordinate?: (value: number) => number | null } | null)?.priceToCoordinate?.(price) ?? null;
  },
  getPriceForY(y: number) {
    return (candleSeries as { coordinateToPrice?: (value: number) => number | null } | null)?.coordinateToPrice?.(y) ?? null;
  },
}));

const legendItems = computed(() =>
  activeLines.value.map((item) => ({
    key: item.key,
    label: item.label,
    color: item.color,
  })),
);

const summaryItems = computed(() => [
  ['代码', props.klineData?.symbol ?? '--'],
  ['周期', formatKlinePeriod(props.klineData?.interval, props.klineData?.range)],
  ['范围', formatKlineRange(props.klineData?.interval, props.klineData?.range)],
]);

const latestCandle = computed(() => candles.value.at(-1) ?? null);
const activeHudCandle = computed(() => {
  if (hoveredAnchor.value) {
    return candles.value.find((candle) => candle.time === hoveredAnchor.value?.time) ?? latestCandle.value;
  }
  return latestCandle.value;
});
const activeCursorTime = computed(() => hoveredAnchor.value?.time ?? latestCandle.value?.time ?? null);

function indicatorPointByTime<T extends { time: string }>(points: T[], time: string | null) {
  if (!points.length) {
    return null;
  }
  if (!time) {
    return points.at(-1) ?? null;
  }
  return points.find((point) => point.time === time) ?? points.at(-1) ?? null;
}

const activeMacd = computed(() => indicatorPointByTime(props.klineData?.indicators.macd ?? [], activeCursorTime.value));
const activeKdj = computed(() => indicatorPointByTime(props.klineData?.indicators.kdj ?? [], activeCursorTime.value));
const activeRsi = computed(() => indicatorPointByTime(calculateRsi(candles.value, 14), activeCursorTime.value)?.value ?? null);
const activeBoll = computed(() => indicatorPointByTime(props.klineData?.indicators.bollinger ?? [], activeCursorTime.value));

function ensureChart() {
  if (chart || !mainChartRef.value) {
    return;
  }
  chart = createChart(mainChartRef.value, {
    autoSize: true,
    height: 420,
    layout: {
      background: { color: 'transparent' },
      textColor: 'rgba(226,232,240,0.72)',
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: 'rgba(148,163,184,0.08)' },
      horzLines: { color: 'rgba(148,163,184,0.08)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  });
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#f97316',
    downColor: '#22c55e',
    borderUpColor: '#f97316',
    borderDownColor: '#22c55e',
    wickUpColor: '#f97316',
    wickDownColor: '#22c55e',
    priceLineVisible: false,
    lastValueVisible: false,
  });
}

function currentPeriodLabel(period: WatchlistDashboardPeriod | undefined) {
  return period === '1W' ? '周K' : period === '1M' ? '月K' : period === '1Y' ? '年K' : '日K';
}

function currentRangeLabel(period: WatchlistDashboardPeriod | undefined) {
  return period === '1W' ? '近5年' : period === '1M' ? '近10年' : period === '1Y' ? '长期' : '近1年';
}

function formatKlinePeriod(interval: string | undefined, range: string | undefined): string {
  if (interval === '1d' && range === '1y') {
    return '日K';
  }
  if (interval === '1wk' && range === '5y') {
    return '周K';
  }
  if (interval === '1mo' && range === '10y') {
    return '月K';
  }
  if (interval === '1mo' && range === 'max') {
    return '年K';
  }
  return interval ?? '--';
}

function formatKlineRange(interval: string | undefined, range: string | undefined): string {
  if (interval === '1d' && range === '1y') {
    return '近1年';
  }
  if (interval === '1wk' && range === '5y') {
    return '近5年';
  }
  if (interval === '1mo' && range === '10y') {
    return '近10年';
  }
  if (interval === '1mo' && range === 'max') {
    return '长期';
  }
  return range ?? '--';
}

function ensureSubChart() {
  if (subChart || !subChartRef.value) {
    return;
  }
  subChart = createChart(subChartRef.value, {
    autoSize: true,
    height: 140,
    layout: {
      background: { color: 'transparent' },
      textColor: 'rgba(148,163,184,0.72)',
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: 'rgba(148,163,184,0.06)' },
      horzLines: { color: 'rgba(148,163,184,0.08)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  });
  volumeSeries = subChart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceLineVisible: false,
    lastValueVisible: false,
    color: 'rgba(255,182,109,0.35)',
  });
  macdHistogramSeries = subChart.addSeries(HistogramSeries, {
    priceLineVisible: false,
    lastValueVisible: false,
    color: 'rgba(255,182,109,0.32)',
  });
  macdDifSeries = subChart.addSeries(LineSeries, {
    color: '#ffd166',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  macdDeaSeries = subChart.addSeries(LineSeries, {
    color: '#7dd3fc',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  kSeries = subChart.addSeries(LineSeries, {
    color: '#ffd166',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  dSeries = subChart.addSeries(LineSeries, {
    color: '#7dd3fc',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  jSeries = subChart.addSeries(LineSeries, {
    color: '#fb7185',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  rsiSeries = subChart.addSeries(LineSeries, {
    color: '#34d399',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
}

function ensureLineSeries(key: string, color: string, lineStyle?: 0 | 2) {
  ensureChart();
  if (!chart) {
    return null;
  }
  if (!lineSeriesMap.has(key)) {
    lineSeriesMap.set(
      key,
      chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        lineStyle,
        priceLineVisible: false,
        lastValueVisible: false,
      }),
    );
  }
  return lineSeriesMap.get(key) ?? null;
}

function clearSubChart() {
  volumeSeries?.setData([]);
  macdHistogramSeries?.setData([]);
  macdDifSeries?.setData([]);
  macdDeaSeries?.setData([]);
  kSeries?.setData([]);
  dSeries?.setData([]);
  jSeries?.setData([]);
  rsiSeries?.setData([]);
}

function renderSubChart() {
  ensureSubChart();
  if (!subChart || !props.klineData) {
    clearSubChart();
    return;
  }
  clearSubChart();
  if (activeSubIndicator.value === 'VOL') {
    volumeSeries?.setData(
      props.klineData.candles.map((candle) => ({
        time: candle.time,
        value: candle.volume ?? 0,
        color: candle.close >= candle.open ? 'rgba(249,115,22,0.45)' : 'rgba(34,197,94,0.35)',
      })),
    );
  } else if (activeSubIndicator.value === 'MACD') {
    macdHistogramSeries?.setData(
      props.klineData.indicators.macd.map((point) => ({
        time: point.time,
        value: point.histogram,
        color: point.histogram >= 0 ? 'rgba(249,115,22,0.45)' : 'rgba(34,197,94,0.4)',
      })),
    );
    macdDifSeries?.setData(props.klineData.indicators.macd.map((point) => ({ time: point.time, value: point.dif })));
    macdDeaSeries?.setData(props.klineData.indicators.macd.map((point) => ({ time: point.time, value: point.dea })));
  } else if (activeSubIndicator.value === 'KDJ') {
    kSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.k })));
    dSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.d })));
    jSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.j })));
  } else {
    rsiSeries?.setData(calculateRsi(props.klineData.candles, 14).filter((point) => !Number.isNaN(point.value)).map((point) => ({ time: point.time, value: point.value })));
  }
  subChart.timeScale().fitContent();
}

function renderChart() {
  ensureChart();
  if (!chart || !candleSeries) {
    return;
  }
  candleSeries.setData(
    candles.value.map((candle) => ({
      time: candle.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    })),
  );
  const activeKeys = new Set(activeLines.value.map((item) => item.key));
  activeLines.value.forEach((item) => {
    ensureLineSeries(item.key, item.color, item.lineStyle)?.setData(item.points.filter((point) => !Number.isNaN(point.value)));
  });
  lineSeriesMap.forEach((series, key) => {
    if (!activeKeys.has(key)) {
      series.setData([]);
    }
  });
  chart.timeScale().fitContent();
  renderSubChart();
}

function handleDraftStart(anchor: { time: string; price: number }) {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.startDraft(anchor);
}

function handleDraftCommit() {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.commitDraft(props.klineData.symbol);
}

function handleDrawingSelect(selection: { id: string | null; append: boolean }) {
  chartStore.selectDrawing(selection.id, { append: selection.append });
}

function handleHoverAnchorChange(anchor: { time: string; price: number } | null) {
  hoveredAnchor.value = anchor;
}

function handleDrawingAnchorCommit(drawingId: string, anchors: { time: string; price: number }[]) {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.updateDrawingAnchors(props.klineData.symbol, drawingId, anchors);
}

function handleDrawingMoveCommit(drawingId: string, anchors: { time: string; price: number }[]) {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.moveDrawing(props.klineData.symbol, drawingId, anchors);
}

function handleDrawingLabelCommit(drawingId: string, text: string) {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.commitLabelEdit(props.klineData.symbol, drawingId, text);
}

function handleLabelEditingChange(editing: boolean) {
  labelEditingActive.value = editing;
}

function handleUndo() {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.undo(props.klineData.symbol);
}

function handleRedo() {
  if (!props.klineData?.symbol) {
    return;
  }
  chartStore.redo(props.klineData.symbol);
}

function handleWindowKeydown(event: KeyboardEvent) {
  if (!props.klineData?.symbol) {
    return;
  }

  if (labelEditingActive.value) {
    return;
  }

  const activeElement = document.activeElement as HTMLElement | null;
  if (
    activeElement &&
    (activeElement.tagName === 'INPUT' ||
      activeElement.tagName === 'TEXTAREA' ||
      activeElement.tagName === 'SELECT' ||
      activeElement.isContentEditable)
  ) {
    return;
  }

  if (event.ctrlKey || event.metaKey) {
    if (event.key.toLowerCase() === 'z' && event.shiftKey) {
      event.preventDefault();
      chartStore.redo(props.klineData.symbol);
      return;
    }
    if (event.key.toLowerCase() === 'z') {
      event.preventDefault();
      chartStore.undo(props.klineData.symbol);
      return;
    }
    if (event.key.toLowerCase() === 'y') {
      event.preventDefault();
      chartStore.redo(props.klineData.symbol);
    }
    return;
  }

  if (event.key === 'Escape') {
    if (chartStore.draft) {
      event.preventDefault();
      chartStore.cancelDraft();
      return;
    }
    if (chartStore.selectedDrawingIds.length) {
      event.preventDefault();
      chartStore.clearSelection();
    }
    return;
  }

  if (chartStore.draft) {
    return;
  }

  if (event.key === 'Delete' || event.key === 'Backspace') {
    if (!chartStore.selectedDrawingIds.length) {
      return;
    }
    event.preventDefault();
    chartStore.deleteSelectedDrawings(props.klineData.symbol);
    return;
  }

  if (!chartStore.selectedDrawingIds.length) {
    return;
  }

  const timeStep = event.key === 'ArrowLeft' ? -(event.shiftKey ? 5 : 1) : event.key === 'ArrowRight' ? (event.shiftKey ? 5 : 1) : 0;
  if (!timeStep && event.key !== 'ArrowUp' && event.key !== 'ArrowDown') {
    return;
  }

  const high = Math.max(...candles.value.map((item) => item.high));
  const low = Math.min(...candles.value.map((item) => item.low));
  const basePriceStep = high > low ? (high - low) * (event.shiftKey ? 0.03 : 0.01) : 1;
  const priceDelta = event.key === 'ArrowUp' ? basePriceStep : event.key === 'ArrowDown' ? -basePriceStep : 0;

  event.preventDefault();
  chartStore.nudgeSelectedDrawings(props.klineData.symbol, {
    candles: candles.value,
    timeStep,
    priceDelta,
  });
}

function currentRangeRatio() {
  if (!candles.value.length) {
    return null;
  }
  const high = Math.max(...candles.value.map((item) => item.high));
  const low = Math.min(...candles.value.map((item) => item.low));
  const latest = latestCandle.value?.close ?? null;
  if (latest === null || high <= low) {
    return null;
  }
  return (latest - low) / (high - low);
}

const dashboardGauges = computed(() => [
  { label: '日内区间', value: activeHudCandle.value ? formatPercent(((activeHudCandle.value.high - activeHudCandle.value.low) / Math.max(activeHudCandle.value.close, 1)) * 100) : '--' },
  { label: '区间位置', value: currentRangeRatio() === null ? '--' : `${Math.round(currentRangeRatio()! * 100)}%` },
  {
    label: '副图',
    value: activeSubIndicator.value,
  },
]);

const technicalReadouts = computed(() => [
  ['收盘', formatNumber(activeHudCandle.value?.close)],
  ['BOLL上轨', formatNumber(activeBoll.value?.upper)],
  ['DIF', formatNumber(activeMacd.value?.dif)],
  ['K', formatNumber(activeKdj.value?.k)],
  ['RSI14', formatNumber(activeRsi.value)],
]);
const subIndicatorRows = computed(() => {
  if (activeSubIndicator.value === 'MACD') {
    return [
      ['DIF', formatNumber(activeMacd.value?.dif)],
      ['DEA', formatNumber(activeMacd.value?.dea)],
      ['柱值', formatNumber(activeMacd.value?.histogram)],
    ];
  }
  if (activeSubIndicator.value === 'KDJ') {
    return [
      ['K', formatNumber(activeKdj.value?.k)],
      ['D', formatNumber(activeKdj.value?.d)],
      ['J', formatNumber(activeKdj.value?.j)],
    ];
  }
  if (activeSubIndicator.value === 'RSI') {
    return [['RSI14', formatNumber(activeRsi.value)]];
  }
  return [['成交量', formatNumber(activeHudCandle.value?.volume, 0)]];
});

watch(
  () => [props.klineData?.symbol, props.klineData?.candles.length],
  () => {
    hoveredAnchor.value = null;
    labelEditingActive.value = false;
    chartStore.selectDrawing(null);
    chartStore.cancelDraft();
    if (props.klineData?.symbol) {
      chartStore.hydrateForSymbol(props.klineData.symbol, props.klineData.candles);
      renderChart();
    }
  },
  { immediate: true },
);

watch(
  () => [props.klineData, chartStore.activeTemplateId, chartStore.subIndicator],
  () => {
    renderChart();
  },
  { deep: true },
);

onMounted(() => {
  renderChart();
  window.addEventListener('keydown', handleWindowKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleWindowKeydown);
  chart?.remove();
  subChart?.remove();
  chartStore.flushAll();
});
</script>

<template>
  <section class="grid gap-4 rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(10,17,27,0.98),rgba(7,12,22,0.98))] p-4" data-role="kline-chart">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">K线图</p>
        <strong class="block text-lg text-text">{{ klineData?.symbol ?? '市场概览' }}</strong>
        <p class="text-xs text-text-faint">{{ klineData?.stale ? '数据可能不是最新' : '更新时间以最新行情返回为准' }}</p>
      </div>
      <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">更新时间 {{ klineData ? '最新' : '--' }}</span>
    </header>

    <div class="grid gap-3 xl:items-start" :class="dashboardCollapsed ? 'xl:grid-cols-[minmax(0,1fr)]' : 'xl:grid-cols-[minmax(0,1fr)_320px]'" data-role="kline-layout-shell" :data-sidebar-collapsed="dashboardCollapsed ? 'true' : 'false'">
      <div class="grid gap-3">
        <KlineToolbar
          :current-period="currentPeriod ?? '1D'"
          :active-tool="chartStore.activeTool"
          :drawing-disabled="overlayDisabled"
          :collapsed="dashboardCollapsed"
          :can-undo="klineData?.symbol ? chartStore.canUndo(klineData.symbol) : false"
          :can-redo="klineData?.symbol ? chartStore.canRedo(klineData.symbol) : false"
          @period-change="emit('switchPeriod', $event)"
          @tool-change="chartStore.selectTool($event)"
          @clear-drawings="klineData?.symbol && chartStore.clearSymbolDrawings(klineData.symbol)"
          @undo="handleUndo"
          @redo="handleRedo"
          @toggle-dashboard="dashboardCollapsed = !dashboardCollapsed"
        />

        <div class="relative overflow-hidden rounded-[18px] border border-border/80 bg-[linear-gradient(180deg,rgba(12,19,29,0.92),rgba(8,13,22,0.94))]" data-role="kline-chart-stage">
          <div class="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-3 p-3">
            <div class="flex max-w-[70%] flex-wrap gap-2" data-role="kline-stage-badges">
              <span v-for="[label, value] in summaryItems" :key="label" class="rounded-full border border-border/70 bg-[rgba(6,10,17,0.72)] px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-text-faint">
                {{ label }} <span class="text-text">{{ value }}</span>
              </span>
            </div>
            <div class="flex flex-wrap justify-end gap-2" data-role="kline-chart-legend">
              <span v-for="item in legendItems" :key="item.key" class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-[rgba(6,10,17,0.72)] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-text-faint">
                <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: item.color }" />
                {{ item.label }}
              </span>
            </div>
          </div>

          <div class="pointer-events-none absolute left-3 top-14 z-10 flex max-w-[calc(100%-1.5rem)] flex-wrap gap-2 rounded-[14px] border border-[rgba(255,183,125,0.18)] bg-[rgba(7,12,22,0.82)] px-3 py-2 text-[11px] uppercase tracking-[0.14em]" data-role="kline-hud">
            <span class="text-text-faint">开 <strong class="ml-1 text-text">{{ formatNumber(activeHudCandle?.open) }}</strong></span>
            <span class="text-text-faint">高 <strong class="ml-1 text-text">{{ formatNumber(activeHudCandle?.high) }}</strong></span>
            <span class="text-text-faint">低 <strong class="ml-1 text-text">{{ formatNumber(activeHudCandle?.low) }}</strong></span>
            <span class="text-text-faint">收 <strong class="ml-1 text-text">{{ formatNumber(activeHudCandle?.close) }}</strong></span>
            <span class="text-text-faint">
              涨跌
              <strong class="ml-1" :class="(activeHudCandle?.close ?? 0) >= (activeHudCandle?.open ?? 0) ? 'text-[#ffca97]' : 'text-[#86efac]'">
                {{ activeHudCandle ? formatPercent(((activeHudCandle.close - activeHudCandle.open) / Math.max(activeHudCandle.open, 1)) * 100) : '--' }}
              </strong>
            </span>
            <span class="text-text-faint">成交量 <strong class="ml-1 text-text">{{ formatNumber(activeHudCandle?.volume, 0) }}</strong></span>
          </div>

          <div class="relative grid gap-0 p-3 pt-24">
            <div class="relative">
              <div ref="mainChartRef" class="h-[440px] w-full" />
              <KlineDrawingOverlay
                :symbol="klineData?.symbol ?? null"
                :candles="candles"
                :drawings="drawings"
                :draft-anchors="chartStore.draft?.anchors ?? null"
                :active-tool="chartStore.activeTool"
                :selected-drawing-id="chartStore.selectedDrawingId"
                :disabled="overlayDisabled"
                :chart-projector="chartProjector"
                @draft-start="handleDraftStart"
                @draft-update="chartStore.updateDraft($event)"
                @draft-commit="handleDraftCommit"
                @draft-cancel="chartStore.cancelDraft()"
                @label-editing-change="handleLabelEditingChange"
                @drawing-select="handleDrawingSelect"
                @hover-anchor-change="handleHoverAnchorChange"
                @drawing-anchor-commit="handleDrawingAnchorCommit"
                @drawing-move-commit="handleDrawingMoveCommit"
                @drawing-label-commit="handleDrawingLabelCommit"
              />
              <KlineDrawingSelectionPopover
                :drawing="selectedDrawing"
                :selected-drawings="selectedDrawings"
                @style-change="klineData?.symbol && selectedDrawing && chartStore.updateDrawingStyle(klineData.symbol, selectedDrawing.id, $event as Partial<KlineDrawingStyle>)"
                @drawing-lock-toggle="klineData?.symbol && selectedDrawing && chartStore.toggleDrawingLocked(klineData.symbol, selectedDrawing.id)"
                @drawing-visible-toggle="klineData?.symbol && selectedDrawing && chartStore.toggleDrawingVisible(klineData.symbol, selectedDrawing.id)"
                @drawing-duplicate="klineData?.symbol && selectedDrawing && (chartStore.selectDrawing(selectedDrawing.id), chartStore.duplicateSelectedDrawings(klineData.symbol))"
                @drawing-delete="klineData?.symbol && selectedDrawing && chartStore.deleteDrawing(klineData.symbol, selectedDrawing.id)"
                @drawing-group-lock-toggle="klineData?.symbol && chartStore.toggleSelectedLocked(klineData.symbol)"
                @drawing-group-visible-toggle="klineData?.symbol && chartStore.toggleSelectedVisible(klineData.symbol)"
                @drawing-group-duplicate="klineData?.symbol && chartStore.duplicateSelectedDrawings(klineData.symbol)"
                @drawing-group-delete="klineData?.symbol && chartStore.deleteSelectedDrawings(klineData.symbol)"
              />
            </div>
            <div class="border-t border-border/60 pt-3">
              <div class="flex flex-wrap items-center justify-between gap-2" data-role="kline-subindicator-strip">
                <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">副图 {{ activeSubIndicator }}</span>
                <div class="flex flex-wrap gap-2">
                  <button type="button" data-role="indicator-switch-vol" class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]" :class="activeSubIndicator === 'VOL' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'" @click="chartStore.setSubIndicator('VOL')">成交量</button>
                  <button type="button" data-role="indicator-switch-macd" class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]" :class="activeSubIndicator === 'MACD' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'" @click="chartStore.setSubIndicator('MACD')">MACD</button>
                  <button type="button" data-role="indicator-switch-kdj" class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]" :class="activeSubIndicator === 'KDJ' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'" @click="chartStore.setSubIndicator('KDJ')">KDJ</button>
                </div>
              </div>
              <div ref="subChartRef" class="mt-3 h-[140px] w-full" />
              <div class="mt-3 grid gap-2 rounded-[14px] border border-border/60 bg-[rgba(255,255,255,0.02)] px-3 py-2.5" data-role="kline-subindicator-panel">
                <div class="flex items-center justify-between gap-3">
                  <span class="text-[10px] uppercase tracking-[0.18em] text-[#ffb77d]">{{ activeSubIndicator }}</span>
                  <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">最新读数</span>
                </div>
                <div class="grid grid-cols-3 gap-2">
                  <article v-for="[label, value] in subIndicatorRows" :key="label" class="grid gap-0.5">
                    <span class="text-[9px] uppercase tracking-[0.18em] text-text-faint">{{ label }}</span>
                    <strong class="text-sm text-text">{{ value }}</strong>
                  </article>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!klineData" class="pointer-events-none absolute inset-0 grid place-items-center bg-[linear-gradient(180deg,rgba(9,14,23,0.82),rgba(9,14,23,0.5))] p-6" data-role="kline-chart-empty-state">
            <div class="grid w-full gap-3">
              <div class="h-4 w-32 animate-pulse rounded-full bg-white/10" />
              <div class="h-6 w-2/3 animate-pulse rounded-full bg-white/10" />
              <div class="h-40 w-full animate-pulse rounded-[16px] bg-white/5" />
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            v-for="event in klineData?.news_events ?? []"
            :key="event.time"
            :data-role="`kline-event-chip-${event.time}`"
            :data-active="highlightedEventTime === event.time ? 'true' : 'false'"
            type="button"
            class="justify-self-start rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.12em]"
            :class="highlightedEventTime === event.time ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffdfba]' : 'border-[rgba(255,159,47,0.26)] text-[#ffca97]'"
            @click="emit('focusNews', event)"
          >
            {{ event.time }} · {{ event.items.length }} 条新闻
          </button>
        </div>
      </div>

      <aside v-if="!dashboardCollapsed" class="grid gap-3" data-role="kline-chart-dashboard">
        <KlineIndicatorWorkbench
          :templates="chartStore.templates"
          :active-template-id="chartStore.activeTemplateId"
          :sub-indicator="activeSubIndicator"
          :disabled="overlayDisabled"
          @template-apply="chartStore.applyTemplate($event)"
          @template-save="chartStore.copyActiveTemplate()"
          @template-delete="chartStore.deleteCustomTemplate($event)"
          @subindicator-change="chartStore.setSubIndicator($event)"
        />

        <div class="grid gap-2 rounded-[14px] border border-border/70 bg-[rgba(255,255,255,0.025)] px-3 py-3">
          <div class="flex items-center justify-between gap-2">
            <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">图表读数</span>
            <strong class="text-sm text-text">{{ formatNumber(activeHudCandle?.close) }}</strong>
          </div>
          <div class="grid gap-2">
            <article v-for="item in dashboardGauges" :key="item.label" class="flex items-center justify-between gap-3">
              <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">{{ item.label }}</span>
              <strong class="text-sm text-text">{{ item.value }}</strong>
            </article>
          </div>
          <div class="grid grid-cols-2 gap-x-3 gap-y-2">
            <article v-for="[label, value] in technicalReadouts" :key="label" class="grid gap-0.5">
              <span class="text-[9px] uppercase tracking-[0.18em] text-text-faint">{{ label }}</span>
              <strong class="text-sm text-text">{{ value }}</strong>
            </article>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>
