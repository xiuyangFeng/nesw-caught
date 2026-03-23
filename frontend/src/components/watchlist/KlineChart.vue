<script setup lang="ts">
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { NewsEventMarker, StockKlineResponse } from '../../types/api';

const props = defineProps<{
  klineData: StockKlineResponse | null;
}>();

defineEmits<{
  focusNews: [event: NewsEventMarker];
}>();

const chartRef = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<'Candlestick'> | null = null;
let volumeSeries: ISeriesApi<'Histogram'> | null = null;
const lineSeriesMap = new Map<string, ISeriesApi<'Line'>>();

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
    class="grid gap-3 rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(10,17,27,0.98),rgba(7,12,22,0.98))] p-4"
    data-role="kline-chart"
  >
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">K-Line</p>
        <strong class="text-text">{{ klineData?.symbol ?? 'Market Overview' }}</strong>
      </div>
      <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">
        {{ klineData?.interval ?? '--' }} / {{ klineData?.range ?? '--' }}
      </span>
    </div>

    <div ref="chartRef" class="h-80 w-full rounded-[18px] border border-border/80 bg-[rgba(255,255,255,0.02)]" />

    <div class="flex flex-wrap gap-2">
      <button
        v-for="event in klineData?.news_events ?? []"
        :key="event.time"
        type="button"
        class="justify-self-start rounded-full border border-[rgba(255,159,47,0.26)] px-2.5 py-1 text-[11px] uppercase tracking-[0.12em] text-[#ffca97]"
        @click="$emit('focusNews', event)"
      >
        {{ event.time }} · {{ event.items.length }} news
      </button>
    </div>
  </section>
</template>
