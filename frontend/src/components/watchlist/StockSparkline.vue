<script setup lang="ts">
import { createChart, LineSeries, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  prices: number[];
}>();

const containerRef = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let lineSeries: ISeriesApi<'Line'> | null = null;

// 涨跌染色：红涨绿跌，数据不足时回落到主色单青。
const strokeColor = computed(() => {
  const prices = props.prices;
  if (prices.length < 2) {
    return '#3ad2e6';
  }
  const delta = prices[prices.length - 1] - prices[0];
  if (delta > 0) return '#ff5a72';
  if (delta < 0) return '#1fd39a';
  return '#3ad2e6';
});

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
  // 真实 lightweight-charts 支持 applyOptions；测试 mock 未实现，用可选链兜底跳过。
  lineSeries.applyOptions?.({ color: strokeColor.value });
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
    color: strokeColor.value,
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
