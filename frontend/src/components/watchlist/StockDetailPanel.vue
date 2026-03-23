<script setup lang="ts">
import { computed, ref } from 'vue';

import type { NewsEventMarker, NewsItem, StockKlineResponse, WatchlistDashboardPeriod, WatchlistQuoteSummary } from '../../types/api';
import IndicatorChart from './IndicatorChart.vue';
import KlineChart from './KlineChart.vue';
import RelatedNewsSidebar from './RelatedNewsSidebar.vue';
import StockMetricsGrid from './StockMetricsGrid.vue';

const props = defineProps<{
  quote: WatchlistQuoteSummary | null;
  klineData: StockKlineResponse | null;
  detailNews: NewsItem[];
  currentPeriod: WatchlistDashboardPeriod;
  klineLoading: boolean;
  klineError: string | null;
}>();

const emit = defineEmits<{
  switchPeriod: [period: WatchlistDashboardPeriod];
}>();

const activeIndicator = ref<'MACD' | 'KDJ' | 'BOLL'>('MACD');
const highlightedEventTime = ref<string | null>(null);

const periods: WatchlistDashboardPeriod[] = ['1D', '1W', '1M', '3M', '1Y'];

const headline = computed(() => props.quote?.display_name ?? props.klineData?.symbol ?? 'Market Overview');

function focusNewsEvent(event: NewsEventMarker) {
  highlightedEventTime.value = event.time;
}

function focusNewsItem(item: NewsItem) {
  highlightedEventTime.value = (item.published_at ?? item.fetched_at).slice(0, 10);
}
</script>

<template>
  <section class="grid gap-4" data-role="stock-detail-panel">
    <header class="flex flex-col gap-3 rounded-[22px] border border-border bg-[linear-gradient(160deg,rgba(20,14,10,0.98),rgba(10,16,26,0.98))] p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Detail Panel</p>
          <h2 class="text-[28px] leading-none text-text">{{ headline }}</h2>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="period in periods"
            :key="period"
            type="button"
            class="rounded-full border px-3 py-1 text-xs uppercase tracking-[0.16em]"
            :class="currentPeriod === period ? 'border-[#ffb66d] text-[#ffca97]' : 'border-border text-text-faint'"
            :data-role="`period-${period}`"
            @click="emit('switchPeriod', period)"
          >
            {{ period }}
          </button>
        </div>
      </div>
      <p class="text-sm text-text-soft">
        {{ klineLoading ? '正在加载最新 K 线...' : klineError ? klineError : '图表、指标和新闻事件在同一面板联动展示。' }}
      </p>
    </header>

    <KlineChart :kline-data="klineData" @focus-news="focusNewsEvent" />
    <IndicatorChart :indicators="klineData?.indicators ?? null" :active-indicator="activeIndicator" @switch-indicator="activeIndicator = $event" />
    <StockMetricsGrid :quote="quote" />

    <div class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <RelatedNewsSidebar :items="detailNews" :highlighted-event-time="highlightedEventTime" @focus-news="focusNewsItem" />
      <section class="rounded-[22px] border border-border bg-[rgba(8,14,23,0.94)] p-4">
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Signal Notes</p>
        <ul class="mt-3 grid gap-2 text-sm text-text-soft">
          <li>主图显示最新 {{ klineData?.candles.length ?? 0 }} 根 K 线。</li>
          <li>当前副图为 {{ activeIndicator }}。</li>
          <li>已关联 {{ klineData?.news_events.length ?? 0 }} 个新闻日期标记。</li>
        </ul>
      </section>
    </div>
  </section>
</template>
