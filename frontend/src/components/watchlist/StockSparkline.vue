<script setup lang="ts">
import { createChart, LineSeries, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  prices: number[];
}>();

const containerRef = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let lineSeries: ISeriesApi<'Line'> | null = null;

function buildData(prices: number[]) {
  return prices.map((value, index) => ({
    time: `2026-01-${String(index + 1).padStart(2, '0')}` as const,
    value,
  }));
}

function renderSeries() {
  if (!lineSeries) {
    return;
  }
  lineSeries.setData(buildData(props.prices));
}

onMounted(() => {
  if (!containerRef.value) {
    return;
  }

  chart = createChart(containerRef.value, {
    autoSize: true,
    height: 44,
    layout: {
      background: { color: 'transparent' },
      textColor: 'rgba(226,232,240,0.72)',
      attributionLogo: false,
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    rightPriceScale: {
      visible: false,
    },
    leftPriceScale: {
      visible: false,
    },
    timeScale: {
      visible: false,
      borderVisible: false,
    },
    crosshair: {
      vertLine: { visible: false, labelVisible: false },
      horzLine: { visible: false, labelVisible: false },
    },
    handleScroll: false,
    handleScale: false,
  });
  lineSeries = chart.addSeries(LineSeries, {
    color: '#ffb66d',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  renderSeries();
  chart.timeScale().fitContent();
});

watch(
  () => props.prices,
  () => {
    renderSeries();
    chart?.timeScale().fitContent();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chart?.remove();
  chart = null;
  lineSeries = null;
});
</script>

<template>
  <div ref="containerRef" class="h-11 w-full" data-role="stock-sparkline" />
</template>
