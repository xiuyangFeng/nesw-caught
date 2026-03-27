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

import type { NewsEventMarker, StockKlineResponse } from '../../types/api';

const props = defineProps<{
  klineData: StockKlineResponse | null;
  highlightedEventTime?: string | null;
}>();

const emit = defineEmits<{
  focusNews: [event: NewsEventMarker];
}>();

const chartRef = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<'Candlestick'> | null = null;
let volumeSeries: ISeriesApi<'Histogram'> | null = null;
const lineSeriesMap = new Map<string, ISeriesApi<'Line'>>();

const legendItems = computed(() => {
  const items = [
    { key: 'ma5', label: 'MA5', color: '#ffd166' },
    { key: 'ma10', label: 'MA10', color: '#7dd3fc' },
    { key: 'ma20', label: 'MA20', color: '#c084fc' },
    { key: 'ma60', label: 'MA60', color: '#fb7185' },
  ];

  if ((props.klineData?.indicators.bollinger.length ?? 0) > 0) {
    items.push({ key: 'boll', label: 'BOLL', color: '#34d399' });
  }

  return items;
});

const summaryItems = computed(() => {
  const klineData = props.klineData;
  return [
    { label: klineData?.symbol ?? 'Market Overview', value: klineData?.symbol ?? '--' },
    { label: 'Interval', value: klineData?.interval ?? '--' },
    { label: 'Range', value: klineData?.range ?? '--' },
    { label: 'Candles', value: klineData?.candles.length.toString() ?? '0' },
  ];
});

function ensureChart() {
  if (chart || !chartRef.value) {
    return;
  }

  chart = createChart(chartRef.value, {
    autoSize: true,
    height: 320,
    layout: {
      background: { color: 'transparent' },
      textColor: 'rgba(226,232,240,0.72)',
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: 'rgba(148,163,184,0.08)' },
      horzLines: { color: 'rgba(148,163,184,0.08)' },
    },
    rightPriceScale: {
      borderVisible: false,
    },
    timeScale: {
      borderVisible: false,
    },
    crosshair: {
      vertLine: { labelVisible: false },
      horzLine: { labelVisible: false },
    },
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

  volumeSeries = chart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceLineVisible: false,
    lastValueVisible: false,
    color: 'rgba(255,182,109,0.35)',
  });

  lineSeriesMap.set(
    'ma5',
    chart.addSeries(LineSeries, {
      color: '#ffd166',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
  lineSeriesMap.set(
    'ma10',
    chart.addSeries(LineSeries, {
      color: '#7dd3fc',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
  lineSeriesMap.set(
    'ma20',
    chart.addSeries(LineSeries, {
      color: '#c084fc',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
  lineSeriesMap.set(
    'ma60',
    chart.addSeries(LineSeries, {
      color: '#fb7185',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
}

function clearChart() {
  candleSeries?.setData([]);
  volumeSeries?.setData([]);
  lineSeriesMap.forEach((series) => series.setData([]));
}

function renderChart() {
  ensureChart();
  if (!chart || !candleSeries || !volumeSeries) {
    return;
  }
  if (!props.klineData) {
    clearChart();
    return;
  }

  candleSeries.setData(
    props.klineData.candles.map((candle) => ({
      time: candle.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    })),
  );

  volumeSeries.setData(
    props.klineData.candles.map((candle) => ({
      time: candle.time,
      value: candle.volume ?? 0,
      color: candle.close >= candle.open ? 'rgba(249,115,22,0.4)' : 'rgba(34,197,94,0.35)',
    })),
  );

  (['ma5', 'ma10', 'ma20', 'ma60'] as const).forEach((key) => {
    lineSeriesMap.get(key)?.setData(props.klineData?.indicators[key] ?? []);
  });

  chart.timeScale().fitContent();
}

onMounted(() => {
  renderChart();
});

watch(
  () => props.klineData,
  () => {
    renderChart();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chart?.remove();
  chart = null;
  candleSeries = null;
  volumeSeries = null;
  lineSeriesMap.clear();
});
</script>

<template>
  <section
    class="grid gap-4 rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(10,17,27,0.98),rgba(7,12,22,0.98))] p-4"
    data-role="kline-chart"
  >
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Trading Desk</p>
        <strong class="block text-lg text-text">{{ klineData?.symbol ?? 'Market Overview' }}</strong>
        <p class="text-xs text-text-faint">{{ klineData?.stale ? 'Data stale' : 'Live chart shell' }}</p>
      </div>
    </header>

    <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
      <div
        class="grid gap-2 rounded-[18px] border border-border/80 bg-[rgba(255,255,255,0.02)] p-3"
        data-role="kline-chart-summary"
      >
        <div class="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.12em] text-text-faint">
          <span
            v-for="item in summaryItems"
            :key="item.label"
            class="rounded-full border border-border/70 px-2.5 py-1"
          >
            {{ item.label }}: <span class="text-text">{{ item.value }}</span>
          </span>
        </div>
      </div>
      <div class="flex flex-wrap justify-start gap-2 md:justify-end" data-role="kline-chart-legend">
        <span
          v-for="item in legendItems"
          :key="item.key"
          class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-[rgba(255,255,255,0.03)] px-3 py-1 text-[11px] uppercase tracking-[0.12em] text-text-faint"
        >
          <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: item.color }" />
          {{ item.label }}
        </span>
      </div>
    </div>

    <div class="relative overflow-hidden rounded-[18px] border border-border/80 bg-[rgba(255,255,255,0.02)]">
      <div ref="chartRef" class="h-80 w-full" />
      <div
        v-if="!klineData"
        class="pointer-events-none absolute inset-0 grid place-items-center bg-[linear-gradient(180deg,rgba(9,14,23,0.82),rgba(9,14,23,0.5))] p-6"
        data-role="kline-chart-empty-state"
      >
        <div class="grid w-full gap-3">
          <div class="h-4 w-32 animate-pulse rounded-full bg-white/10" />
          <div class="h-6 w-2/3 animate-pulse rounded-full bg-white/10" />
          <div class="h-24 w-full animate-pulse rounded-[16px] bg-white/5" />
        </div>
      </div>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="event in klineData?.news_events ?? []"
        :key="event.time"
        :data-role="`kline-event-chip-${event.time}`"
        :data-active="props.highlightedEventTime === event.time ? 'true' : 'false'"
        type="button"
        class="justify-self-start rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.12em]"
        :class="
          props.highlightedEventTime === event.time
            ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffdfba]'
            : 'border-[rgba(255,159,47,0.26)] text-[#ffca97]'
        "
        @click="emit('focusNews', event)"
      >
        {{ event.time }} · {{ event.items.length }} news
      </button>
    </div>
  </section>
</template>
