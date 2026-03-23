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

const indicatorState = computed(() => ({
  MACD: (props.indicators?.macd.length ?? 0) > 0,
  KDJ: (props.indicators?.kdj.length ?? 0) > 0,
  BOLL: (props.indicators?.bollinger.length ?? 0) > 0,
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
  primarySeries = chart.addSeries(LineSeries, { color: '#ffb66d', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  secondarySeries = chart.addSeries(LineSeries, { color: '#7dd3fc', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  tertiarySeries = chart.addSeries(LineSeries, { color: '#c084fc', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  histogramSeries = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false, color: 'rgba(255,182,109,0.35)' });
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
  if (props.activeIndicator === 'MACD') {
    primarySeries.setData(props.indicators.macd.map((item) => ({ time: item.time, value: item.dif })));
    secondarySeries.setData(props.indicators.macd.map((item) => ({ time: item.time, value: item.dea })));
    histogramSeries.setData(
      props.indicators.macd.map((item) => ({
        time: item.time,
        value: item.histogram,
        color: item.histogram >= 0 ? 'rgba(249,115,22,0.38)' : 'rgba(34,197,94,0.32)',
      })),
    );
  } else if (props.activeIndicator === 'KDJ') {
    primarySeries.setData(props.indicators.kdj.map((item) => ({ time: item.time, value: item.k })));
    secondarySeries.setData(props.indicators.kdj.map((item) => ({ time: item.time, value: item.d })));
    tertiarySeries.setData(props.indicators.kdj.map((item) => ({ time: item.time, value: item.j })));
  } else {
    primarySeries.setData(props.indicators.bollinger.map((item) => ({ time: item.time, value: item.upper })));
    secondarySeries.setData(props.indicators.bollinger.map((item) => ({ time: item.time, value: item.middle })));
    tertiarySeries.setData(props.indicators.bollinger.map((item) => ({ time: item.time, value: item.lower })));
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
  <section class="grid gap-3 rounded-[22px] border border-border bg-[rgba(8,14,23,0.94)] p-4">
    <div class="flex flex-wrap gap-2">
      <button
        v-for="indicator in ['MACD', 'KDJ', 'BOLL']"
        :key="indicator"
        type="button"
        class="rounded-full border px-3 py-1 text-xs uppercase tracking-[0.14em]"
        :class="
          activeIndicator === indicator
            ? 'border-[#ffb66d] text-[#ffca97]'
            : 'border-border text-text-faint'
        "
        :data-role="`indicator-${indicator}`"
        :disabled="!indicatorState[indicator as 'MACD' | 'KDJ' | 'BOLL']"
        @click="emit('switchIndicator', indicator as 'MACD' | 'KDJ' | 'BOLL')"
      >
        {{ indicator }}
      </button>
    </div>
    <div ref="chartRef" class="h-[180px] w-full rounded-[18px] border border-border/80 bg-[rgba(255,255,255,0.02)]" />
  </section>
</template>
