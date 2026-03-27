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

import type { NewsEventMarker, StockKlineResponse, WatchlistDashboardPeriod } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';

const props = defineProps<{
  klineData: StockKlineResponse | null;
  currentPeriod?: WatchlistDashboardPeriod;
  highlightedEventTime?: string | null;
}>();

const emit = defineEmits<{
  focusNews: [event: NewsEventMarker];
  switchPeriod: [period: WatchlistDashboardPeriod];
}>();

const mainChartRef = ref<HTMLElement | null>(null);
const subChartRef = ref<HTMLElement | null>(null);
const activeSubIndicator = ref<'VOL' | 'MACD' | 'KDJ'>('VOL');
const dashboardCollapsed = ref(false);

let chart: IChartApi | null = null;
let subChart: IChartApi | null = null;
let candleSeries: ISeriesApi<'Candlestick'> | null = null;
const lineSeriesMap = new Map<string, ISeriesApi<'Line'>>();
let volumeSeries: ISeriesApi<'Histogram'> | null = null;
let macdHistogramSeries: ISeriesApi<'Histogram'> | null = null;
let macdDifSeries: ISeriesApi<'Line'> | null = null;
let macdDeaSeries: ISeriesApi<'Line'> | null = null;
let kSeries: ISeriesApi<'Line'> | null = null;
let dSeries: ISeriesApi<'Line'> | null = null;
let jSeries: ISeriesApi<'Line'> | null = null;

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

const candles = computed(() => props.klineData?.candles ?? []);
const latestCandle = computed(() => candles.value.at(-1) ?? null);
const latestMacd = computed(() => props.klineData?.indicators.macd.at(-1) ?? null);
const latestKdj = computed(() => props.klineData?.indicators.kdj.at(-1) ?? null);
const latestBoll = computed(() => props.klineData?.indicators.bollinger.at(-1) ?? null);
const subIndicatorLabelMap: Record<'VOL' | 'MACD' | 'KDJ', string> = {
  VOL: '成交量',
  MACD: 'MACD',
  KDJ: 'KDJ',
};
const activeSubIndicatorLabel = computed(() => subIndicatorLabelMap[activeSubIndicator.value]);
const periods: Array<{ value: WatchlistDashboardPeriod; label: string }> = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
  { value: '1Y', label: '年K' },
];

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

function clampRatio(value: number | null): number | null {
  if (value === null || Number.isNaN(value)) {
    return null;
  }
  return Math.max(0, Math.min(1, value));
}

function formatRatio(value: number | null): string {
  if (value === null) {
    return '--';
  }
  return `${Math.round(value * 100)}%`;
}

function latestValue(points: Array<{ value: number }> | undefined): number | null {
  if (!points?.length) {
    return null;
  }
  return points.at(-1)?.value ?? null;
}

const sessionRangeRatio = computed(() => {
  const candle = latestCandle.value;
  if (!candle || candle.high <= candle.low) {
    return null;
  }
  return clampRatio((candle.close - candle.low) / (candle.high - candle.low));
});

const rangeRatio = computed(() => {
  if (!candles.value.length) {
    return null;
  }
  const high = Math.max(...candles.value.map((item) => item.high));
  const low = Math.min(...candles.value.map((item) => item.low));
  const latest = latestCandle.value?.close ?? null;
  if (latest === null || high <= low) {
    return null;
  }
  return clampRatio((latest - low) / (high - low));
});

const averageVolume20 = computed(() => {
  const volumes = candles.value.slice(-20).map((item) => item.volume).filter((item): item is number => item !== null);
  if (!volumes.length) {
    return null;
  }
  return volumes.reduce((sum, value) => sum + value, 0) / volumes.length;
});

const dashboardGauges = computed(() => [
  {
    label: '日内区间',
    value: formatRatio(sessionRangeRatio.value),
    ratio: sessionRangeRatio.value ?? 0,
  },
  {
    label: '区间位置',
    value: formatRatio(rangeRatio.value),
    ratio: rangeRatio.value ?? 0,
  },
  {
    label: '偏离MA20',
    value:
      latestCandle.value && latestValue(props.klineData?.indicators.ma20)
        ? formatPercent(((latestCandle.value.close - (latestValue(props.klineData?.indicators.ma20) ?? 0)) / (latestValue(props.klineData?.indicators.ma20) ?? 1)) * 100)
        : '--',
    ratio:
      latestCandle.value && latestValue(props.klineData?.indicators.ma20)
        ? clampRatio(0.5 + ((latestCandle.value.close - (latestValue(props.klineData?.indicators.ma20) ?? 0)) / (latestValue(props.klineData?.indicators.ma20) ?? 1)) * 2)
        : 0,
  },
]);

const technicalReadouts = computed(() => [
  ['MA5', formatNumber(latestValue(props.klineData?.indicators.ma5))],
  ['MA10', formatNumber(latestValue(props.klineData?.indicators.ma10))],
  ['MA20', formatNumber(latestValue(props.klineData?.indicators.ma20))],
  ['MA60', formatNumber(latestValue(props.klineData?.indicators.ma60))],
  ['BOLL上轨', formatNumber(latestBoll.value?.upper)],
  ['BOLL中轨', formatNumber(latestBoll.value?.middle)],
  ['BOLL下轨', formatNumber(latestBoll.value?.lower)],
  ['20日均量', formatNumber(averageVolume20.value, 0)],
]);

const subIndicatorRows = computed(() => {
  if (activeSubIndicator.value === 'MACD') {
    return [
      ['DIF', formatNumber(latestMacd.value?.dif)],
      ['DEA', formatNumber(latestMacd.value?.dea)],
      ['柱值', formatNumber(latestMacd.value?.histogram)],
    ];
  }
  if (activeSubIndicator.value === 'KDJ') {
    return [
      ['K', formatNumber(latestKdj.value?.k)],
      ['D', formatNumber(latestKdj.value?.d)],
      ['J', formatNumber(latestKdj.value?.j)],
    ];
  }
  return [
    ['成交量', formatNumber(latestCandle.value?.volume, 0)],
    ['20日均量', formatNumber(averageVolume20.value, 0)],
    ['收盘', formatNumber(latestCandle.value?.close)],
  ];
});

const summaryItems = computed(() => {
  const klineData = props.klineData;
  return [
    { label: '代码', value: klineData?.symbol ?? '--' },
    { label: '周期', value: formatKlinePeriod(klineData?.interval, klineData?.range) },
    { label: '范围', value: formatKlineRange(klineData?.interval, klineData?.range) },
    { label: 'K线数', value: klineData?.candles.length.toString() ?? '0' },
  ];
});

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
  lineSeriesMap.set(
    'bollUpper',
    chart.addSeries(LineSeries, {
      color: 'rgba(52,211,153,0.65)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
  lineSeriesMap.set(
    'bollMiddle',
    chart.addSeries(LineSeries, {
      color: 'rgba(52,211,153,0.45)',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
  lineSeriesMap.set(
    'bollLower',
    chart.addSeries(LineSeries, {
      color: 'rgba(52,211,153,0.65)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    }),
  );
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
    rightPriceScale: {
      borderVisible: false,
      scaleMargins: {
        top: 0.12,
        bottom: 0.12,
      },
    },
    timeScale: {
      borderVisible: false,
    },
    crosshair: {
      vertLine: { labelVisible: false },
      horzLine: { labelVisible: false },
    },
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
}

function clearChart() {
  candleSeries?.setData([]);
  lineSeriesMap.forEach((series) => series.setData([]));
}

function clearSubChart() {
  volumeSeries?.setData([]);
  macdHistogramSeries?.setData([]);
  macdDifSeries?.setData([]);
  macdDeaSeries?.setData([]);
  kSeries?.setData([]);
  dSeries?.setData([]);
  jSeries?.setData([]);
}

function renderSubChart() {
  ensureSubChart();
  if (!subChart) {
    return;
  }
  clearSubChart();
  if (!props.klineData) {
    return;
  }

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
  } else {
    kSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.k })));
    dSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.d })));
    jSeries?.setData(props.klineData.indicators.kdj.map((point) => ({ time: point.time, value: point.j })));
  }

  subChart.timeScale().fitContent();
}

function renderChart() {
  ensureChart();
  if (!chart || !candleSeries) {
    return;
  }
  if (!props.klineData) {
    clearChart();
    renderSubChart();
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

  (['ma5', 'ma10', 'ma20', 'ma60'] as const).forEach((key) => {
    lineSeriesMap.get(key)?.setData(props.klineData?.indicators[key] ?? []);
  });
  lineSeriesMap.get('bollUpper')?.setData(props.klineData.indicators.bollinger.map((point) => ({ time: point.time, value: point.upper })));
  lineSeriesMap.get('bollMiddle')?.setData(props.klineData.indicators.bollinger.map((point) => ({ time: point.time, value: point.middle })));
  lineSeriesMap.get('bollLower')?.setData(props.klineData.indicators.bollinger.map((point) => ({ time: point.time, value: point.lower })));

  chart.timeScale().fitContent();
  renderSubChart();
}

onMounted(() => {
  renderChart();
});

watch(
  [() => props.klineData, activeSubIndicator],
  () => {
    renderChart();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chart?.remove();
  subChart?.remove();
  chart = null;
  subChart = null;
  candleSeries = null;
  volumeSeries = null;
  macdHistogramSeries = null;
  macdDifSeries = null;
  macdDeaSeries = null;
  kSeries = null;
  dSeries = null;
  jSeries = null;
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
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">K线图</p>
        <strong class="block text-lg text-text">{{ klineData?.symbol ?? '市场概览' }}</strong>
        <p class="text-xs text-text-faint">{{ klineData?.stale ? '数据可能不是最新' : '更新时间以最新行情返回为准' }}</p>
      </div>
      <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">更新时间 {{ klineData ? '最新' : '--' }}</span>
    </header>

    <div
      class="grid gap-3 xl:items-start"
      :class="dashboardCollapsed ? 'xl:grid-cols-[minmax(0,1fr)]' : 'xl:grid-cols-[minmax(0,1fr)_292px]'"
      data-role="kline-layout-shell"
      :data-sidebar-collapsed="dashboardCollapsed ? 'true' : 'false'"
    >
      <div
        class="grid gap-3"
      >
        <div class="flex flex-wrap items-center justify-between gap-2 rounded-[16px] border border-border/70 bg-[rgba(255,255,255,0.02)] px-3 py-2.5" data-role="kline-period-toolbar">
          <div class="flex flex-wrap gap-2">
            <button
              v-for="period in periods"
              :key="period.value"
              type="button"
              class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
              :class="currentPeriod === period.value ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
              :data-role="`period-chip-${period.value}`"
              :data-active="currentPeriod === period.value ? 'true' : 'false'"
              @click="emit('switchPeriod', period.value)"
            >
              {{ period.label }}
            </button>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              data-role="toggle-dashboard"
              class="rounded-full border border-border/70 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-faint"
              @click="dashboardCollapsed = !dashboardCollapsed"
            >
              {{ dashboardCollapsed ? '展开面板' : '收起面板' }}
            </button>
            <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">快速切换周期</span>
          </div>
        </div>

        <div class="grid gap-3 rounded-[16px] border border-border/80 bg-[rgba(255,255,255,0.02)] p-3" data-role="kline-chart-summary">
          <div class="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.12em] text-text-faint">
            <span
              v-for="item in summaryItems"
              :key="item.label"
              class="rounded-full border border-border/70 px-2.5 py-1"
            >
              {{ item.label }}: <span class="text-text">{{ item.value }}</span>
            </span>
          </div>
          <div class="flex flex-wrap justify-start gap-2" data-role="kline-chart-legend">
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
          <div class="grid gap-0 p-3">
            <div ref="mainChartRef" class="h-[440px] w-full" />
            <div class="border-t border-border/60 pt-3">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-role="indicator-switch-vol"
                    class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
                    :class="activeSubIndicator === 'VOL' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
                    @click="activeSubIndicator = 'VOL'"
                  >
                    成交量
                  </button>
                  <button
                    type="button"
                    data-role="indicator-switch-macd"
                    class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
                    :class="activeSubIndicator === 'MACD' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
                    @click="activeSubIndicator = 'MACD'"
                  >
                    MACD
                  </button>
                  <button
                    type="button"
                    data-role="indicator-switch-kdj"
                    class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.16em]"
                    :class="activeSubIndicator === 'KDJ' ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]' : 'border-border/70 text-text-faint'"
                    @click="activeSubIndicator = 'KDJ'"
                  >
                    KDJ
                  </button>
                </div>
                <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">副图 {{ activeSubIndicatorLabel }}</span>
              </div>
              <div ref="subChartRef" class="mt-3 h-[140px] w-full" />
              <div class="mt-3 grid gap-2 rounded-[14px] border border-border/60 bg-[rgba(255,255,255,0.02)] px-3 py-2.5" data-role="kline-subindicator-panel">
                <div class="flex items-center justify-between gap-3">
                  <span class="text-[10px] uppercase tracking-[0.18em] text-[#ffb77d]">{{ activeSubIndicatorLabel }}</span>
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
          <div
            v-if="!klineData"
            class="pointer-events-none absolute inset-0 grid place-items-center bg-[linear-gradient(180deg,rgba(9,14,23,0.82),rgba(9,14,23,0.5))] p-6"
            data-role="kline-chart-empty-state"
          >
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
            {{ event.time }} · {{ event.items.length }} 条新闻
          </button>
        </div>
      </div>

      <aside
        v-if="!dashboardCollapsed"
        class="grid gap-3 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(180deg,rgba(15,22,34,0.98),rgba(9,14,22,0.98))] p-3"
        data-role="kline-chart-dashboard"
      >
        <div class="grid gap-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-[10px] uppercase tracking-[0.18em] text-[#ffb77d]">指标面板</span>
            <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">{{ activeSubIndicatorLabel }}</span>
          </div>
          <div class="grid gap-2">
            <article v-for="item in dashboardGauges" :key="item.label" class="grid gap-1 rounded-[14px] border border-border/70 bg-[rgba(255,255,255,0.025)] px-3 py-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">{{ item.label }}</span>
                <strong class="text-sm text-text">{{ item.value }}</strong>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-[rgba(148,163,184,0.12)]">
                <div class="h-full rounded-full bg-[linear-gradient(90deg,#ff8f3f,#ffd28a)]" :style="{ width: `${Math.round(item.ratio * 100)}%` }" />
              </div>
            </article>
          </div>
        </div>

        <div class="grid gap-2 rounded-[14px] border border-border/70 bg-[rgba(255,255,255,0.025)] px-3 py-3">
          <div class="flex items-center justify-between gap-2">
            <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">技术读数</span>
            <strong class="text-sm text-text">{{ formatNumber(latestCandle?.close) }}</strong>
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
