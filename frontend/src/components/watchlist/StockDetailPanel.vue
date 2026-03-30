<script setup lang="ts">
import { computed, ref } from 'vue';

import type { NewsEventMarker, NewsItem, StockKlineResponse, WatchlistDashboardPeriod, WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime } from '../../utils/time';
import KlineChart from './KlineChart.vue';
import ResearchBriefPanel from './ResearchBriefPanel.vue';
import RelatedNewsSidebar from './RelatedNewsSidebar.vue';

const props = defineProps<{
  quote: WatchlistQuoteSummary | null;
  klineData: StockKlineResponse | null;
  detailNews: NewsItem[];
  researchBrief: import('../../types/api').WatchlistResearchBrief | null;
  currentPeriod: WatchlistDashboardPeriod;
  klineLoading: boolean;
  klineError: string | null;
}>();

const emit = defineEmits<{
  switchPeriod: [period: WatchlistDashboardPeriod];
}>();

const highlightedEventTime = ref<string | null>(null);

const headline = computed(() => props.quote?.display_name ?? props.klineData?.symbol ?? '市场概览');
const symbolLabel = computed(() => props.quote?.symbol ?? props.klineData?.symbol ?? '--');
const lastPrice = computed(() => {
  if (props.quote?.price === null || props.quote?.price === undefined) {
    return '--';
  }
  return props.quote.price.toFixed(2);
});
const changeAmount = computed(() => {
  const value = props.quote?.change_amount;
  if (value === null || value === undefined) {
    return '--';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
});
const updatedAt = computed(() => {
  if (!props.quote?.fetched_at || !props.quote?.market) {
    return '--';
  }
  return formatMarketTime(props.quote.fetched_at, props.quote.market);
});

const candles = computed(() => props.klineData?.candles ?? []);

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

const amplitude = computed(() => {
  if (!props.quote?.previous_close || props.quote.day_high === null || props.quote.day_low === null) {
    return null;
  }
  return ((props.quote.day_high - props.quote.day_low) / props.quote.previous_close) * 100;
});

const sessionPosition = computed(() => {
  const price = props.quote?.price ?? candles.value.at(-1)?.close ?? null;
  const low = props.quote?.day_low ?? null;
  const high = props.quote?.day_high ?? null;
  if (price === null || low === null || high === null || high <= low) {
    return null;
  }
  return clampRatio((price - low) / (high - low));
});

const sixMonthPosition = computed(() => {
  if (!candles.value.length) {
    return null;
  }
  const latest = candles.value.at(-1)?.close ?? null;
  const low = Math.min(...candles.value.map((item) => item.low));
  const high = Math.max(...candles.value.map((item) => item.high));
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

const quoteMetrics = computed(() => [
  ['开盘', formatNumber(props.quote?.open_price)],
  ['昨收', formatNumber(props.quote?.previous_close)],
  ['最高', formatNumber(props.quote?.day_high)],
  ['最低', formatNumber(props.quote?.day_low)],
  ['成交量', formatNumber(props.quote?.volume, 0)],
  ['振幅', formatPercent(amplitude.value)],
  ['日内位置', formatRatio(sessionPosition.value)],
  ['20日均量', formatNumber(averageVolume20.value, 0)],
  ['区间位置', formatRatio(sixMonthPosition.value)],
]);

function focusNewsEvent(event: NewsEventMarker) {
  highlightedEventTime.value = event.time;
}

function focusNewsItem(item: NewsItem) {
  highlightedEventTime.value = (item.published_at ?? item.fetched_at).slice(0, 10);
}
</script>

<template>
  <section class="grid gap-4" data-role="stock-detail-panel">
    <header
      class="grid gap-2 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(155deg,rgba(18,24,35,0.98),rgba(9,13,21,0.99))] px-3 py-3 shadow-[0_14px_34px_rgba(2,6,12,0.28)]"
      data-role="trading-desk-summary"
    >
      <div class="grid gap-3 xl:grid-cols-[minmax(220px,0.78fr)_minmax(0,1.22fr)] xl:items-center">
        <div class="grid gap-1.5" data-role="trading-desk-price-strip">
          <div class="grid gap-0.5">
            <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">行情看盘</p>
            <div class="flex flex-wrap items-end gap-x-2 gap-y-1">
              <h2 class="text-[24px] font-semibold leading-none text-text">{{ headline }}</h2>
              <span class="text-[11px] uppercase tracking-[0.22em] text-text-faint">{{ symbolLabel }}</span>
            </div>
          </div>
          <div class="flex flex-wrap items-end gap-x-2.5 gap-y-1">
            <strong class="text-[34px] font-semibold leading-none text-text">{{ lastPrice }}</strong>
            <div class="grid gap-0.5">
              <span class="text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ changeAmount }}
              </span>
              <span class="text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ formatPercent(quote?.change_percent) }}
              </span>
            </div>
          </div>
        </div>
        <div
          class="grid gap-1.5 rounded-[14px] border border-[rgba(148,163,184,0.1)] bg-[rgba(255,255,255,0.025)] px-3 py-2.5"
          data-role="terminal-quote-matrix"
        >
          <div class="grid grid-cols-2 gap-x-3 gap-y-1.5 md:grid-cols-3 xl:grid-cols-3">
            <article v-for="[label, value] in quoteMetrics" :key="label" class="grid gap-0.5">
              <span class="text-[9px] uppercase tracking-[0.18em] text-text-faint">{{ label }}</span>
              <strong class="text-sm text-text">{{ value }}</strong>
            </article>
          </div>
        </div>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2 text-[13px] text-text-soft">
        <p>
          {{ klineLoading ? '正在加载最新K线图...' : klineError ? klineError : '上方可快速切换周期，主图与右侧面板分别负责趋势观察和技术读数。' }}
        </p>
        <span class="text-[11px] uppercase tracking-[0.16em] text-text-faint">更新时间 {{ updatedAt }}</span>
      </div>
    </header>

    <section data-role="trading-desk-main">
      <KlineChart
        :kline-data="klineData"
        :current-period="currentPeriod"
        :highlighted-event-time="highlightedEventTime"
        @focus-news="focusNewsEvent"
        @switch-period="emit('switchPeriod', $event)"
      />
    </section>

    <section v-if="researchBrief" data-role="watchlist-detail-research">
      <ResearchBriefPanel :research-brief="researchBrief" />
    </section>

    <section class="grid gap-4" data-role="watchlist-detail-news">
      <RelatedNewsSidebar :items="detailNews" :highlighted-event-time="highlightedEventTime" @focus-news="focusNewsItem" />
    </section>
  </section>
</template>
