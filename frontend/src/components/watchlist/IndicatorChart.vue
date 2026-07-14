<script setup lang="ts">
import { HistogramSeries, LineSeries, createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { KlineIndicators } from '../../types/api';

const props = defineProps<{
  indicators: KlineIndicators | null;
  activeIndicator: 'MACD' | 'KDJ' | 'BOLL';
}>();

const emit = defineEmits<{
  switchIndicator: [indicator: 'MACD' | 'KDJ' | 'BOLL'];
}>();

// 后端 IndicatorSeriesView 中各序列字段为可选(缺省即空序列),统一兜底为空数组。
const series = computed(() => ({
  macd: props.indicators?.macd ?? [],
  kdj: props.indicators?.kdj ?? [],
  bollinger: props.indicators?.bollinger ?? [],
}));

const indicatorState = computed(() => ({
  MACD: series.value.macd.length > 0,
  KDJ: series.value.kdj.length > 0,
  BOLL: series.value.bollinger.length > 0,
}));

const chartRef = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let primarySeries: ISeriesApi<'Line'> | null = null;
let secondarySeries: ISeriesApi<'Line'> | null = null;
let tertiarySeries: ISeriesApi<'Line'> | null = null;
let histogramSeries: ISeriesApi<'Histogram'> | null = null;

function ensureChart() {
  if (chart || !chartRef.value) {
    return;
  }
  chart = createChart(chartRef.value, {
    autoSize: true,
    height: 180,
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
  primarySeries = chart.addSeries(LineSeries, { color: '#3ad2e6', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  secondarySeries = chart.addSeries(LineSeries, { color: '#5fb8ff', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  tertiarySeries = chart.addSeries(LineSeries, { color: '#8b7cff', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  histogramSeries = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false, color: 'rgba(58,210,230,0.28)' });
}

function clearSeries() {
  primarySeries?.setData([]);
  secondarySeries?.setData([]);
  tertiarySeries?.setData([]);
  histogramSeries?.setData([]);
}

function renderIndicator() {
  ensureChart();
  if (!chart || !primarySeries || !secondarySeries || !tertiarySeries || !histogramSeries) {
    return;
  }
  if (!props.indicators) {
    clearSeries();
    return;
  }
  clearSeries();
  const { macd, kdj, bollinger } = series.value;
  if (props.activeIndicator === 'MACD') {
    primarySeries.setData(macd.map((item) => ({ time: item.time, value: item.dif })));
    secondarySeries.setData(macd.map((item) => ({ time: item.time, value: item.dea })));
    histogramSeries.setData(
      macd.map((item) => ({
        time: item.time,
        value: item.histogram,
        color: item.histogram >= 0 ? 'rgba(255,90,114,0.4)' : 'rgba(31,211,154,0.36)',
      })),
    );
  } else if (props.activeIndicator === 'KDJ') {
    primarySeries.setData(kdj.map((item) => ({ time: item.time, value: item.k })));
    secondarySeries.setData(kdj.map((item) => ({ time: item.time, value: item.d })));
    tertiarySeries.setData(kdj.map((item) => ({ time: item.time, value: item.j })));
  } else {
    primarySeries.setData(bollinger.map((item) => ({ time: item.time, value: item.upper })));
    secondarySeries.setData(bollinger.map((item) => ({ time: item.time, value: item.middle })));
    tertiarySeries.setData(bollinger.map((item) => ({ time: item.time, value: item.lower })));
  }
  chart.timeScale().fitContent();
}

onMounted(() => {
  renderIndicator();
});

watch(
  () => [props.indicators, props.activeIndicator],
  () => {
    renderIndicator();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chart?.remove();
  chart = null;
});
</script>

<template>
  <section class="grid gap-3 rounded-lg border border-border bg-panel p-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-[11px] uppercase tracking-[0.22em] text-accent">Secondary Panel</p>
        <strong class="text-sm text-text">Indicator Desk</strong>
      </div>
      <div class="flex flex-wrap gap-2 rounded-md border border-border bg-panel-strong p-1">
      <button
        v-for="indicator in ['MACD', 'KDJ', 'BOLL']"
        :key="indicator"
        type="button"
        class="rounded-md border px-3 py-1.5 text-xs uppercase tracking-[0.14em] transition"
        :class="
          activeIndicator === indicator
            ? 'border-accent/60 bg-accent/10 text-accent'
            : 'border-transparent text-text-faint'
        "
        :data-role="`indicator-${indicator}`"
        :disabled="!indicatorState[indicator as 'MACD' | 'KDJ' | 'BOLL']"
        @click="emit('switchIndicator', indicator as 'MACD' | 'KDJ' | 'BOLL')"
      >
        {{ indicator }}
      </button>
      </div>
    </div>
    <div ref="chartRef" class="h-[180px] w-full rounded-[18px] border border-border/80 bg-[rgba(255,255,255,0.02)]" />
  </section>
</template>
