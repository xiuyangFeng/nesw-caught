<script setup lang="ts">
import { computed, ref } from 'vue';

import type { NewsEventMarker, NewsItem, StockKlineResponse, WatchlistDashboardPeriod, WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime } from '../../utils/time';
import KlineChart from './KlineChart.vue';
import RelatedNewsSidebar from './RelatedNewsSidebar.vue';

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

const highlightedEventTime = ref<string | null>(null);
const settingsOpen = ref(false);

const periods: WatchlistDashboardPeriod[] = ['1D', '1W', '1M', '3M', '1Y'];

const headline = computed(() => props.quote?.display_name ?? props.klineData?.symbol ?? 'Market Overview');
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
      class="grid gap-4 rounded-[20px] border border-[rgba(148,163,184,0.16)] bg-[linear-gradient(155deg,rgba(18,24,35,0.98),rgba(9,13,21,0.99))] p-5 shadow-[0_18px_46px_rgba(2,6,12,0.34)]"
      data-role="trading-desk-summary"
    >
      <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div class="grid gap-2">
          <div>
            <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Trading Desk</p>
            <div class="mt-2 flex flex-wrap items-end gap-x-3 gap-y-2">
              <h2 class="text-[30px] font-semibold leading-none text-text">{{ headline }}</h2>
              <span class="text-[12px] uppercase tracking-[0.22em] text-text-faint">{{ symbolLabel }}</span>
            </div>
          </div>
          <div class="flex flex-wrap items-end gap-x-4 gap-y-2">
            <strong class="text-[42px] font-semibold leading-none text-text">{{ lastPrice }}</strong>
            <div class="grid gap-1">
              <span class="text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ changeAmount }}
              </span>
              <span class="text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ formatPercent(quote?.change_percent) }}
              </span>
            </div>
          </div>
        </div>
        <div class="relative self-start">
          <button
            type="button"
            class="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[rgba(148,163,184,0.2)] bg-[rgba(255,255,255,0.04)] text-lg text-text-faint transition hover:border-[#ffb66d] hover:text-[#ffca97]"
            data-role="watchlist-settings-trigger"
            @click="settingsOpen = !settingsOpen"
          >
            ⚙
          </button>
          <div
            v-if="settingsOpen"
            class="absolute right-0 top-12 z-20 w-[280px] rounded-[18px] border border-[rgba(148,163,184,0.16)] bg-[linear-gradient(180deg,rgba(10,17,27,0.98),rgba(7,12,22,0.99))] p-3 shadow-[0_18px_40px_rgba(2,6,12,0.34)]"
            data-role="watchlist-settings-popover"
          >
            <div class="grid gap-3">
              <div class="flex items-center justify-between gap-2">
                <div>
                  <p class="text-[10px] uppercase tracking-[0.18em] text-[#ffb77d]">Settings</p>
                  <strong class="text-sm text-text">图表工具</strong>
                </div>
                <button
                  type="button"
                  class="rounded-full border border-border px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-text-faint"
                  @click="settingsOpen = false"
                >
                  关闭
                </button>
              </div>
              <div class="grid max-h-[220px] gap-3 overflow-y-auto pr-1" data-role="watchlist-settings-scroll">
                <section class="grid gap-2">
                  <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">周期</span>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="period in periods"
                      :key="period"
                      type="button"
                      class="rounded-md border px-3 py-1.5 text-xs uppercase tracking-[0.16em]"
                      :class="
                        currentPeriod === period
                          ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.12)] text-[#ffca97]'
                          : 'border-[rgba(148,163,184,0.18)] text-text-faint'
                      "
                      :data-role="`period-${period}`"
                      @click="emit('switchPeriod', period)"
                    >
                      {{ period }}
                    </button>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article
          v-for="[label, value] in [
            ['Open', formatNumber(quote?.open_price)],
            ['Prev Close', formatNumber(quote?.previous_close)],
            ['High', formatNumber(quote?.day_high)],
            ['Low', formatNumber(quote?.day_low)],
            ['Volume', formatNumber(quote?.volume, 0)],
          ]"
          :key="label"
          class="rounded-[14px] border border-[rgba(148,163,184,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5"
        >
          <span class="block text-[10px] uppercase tracking-[0.18em] text-text-faint">{{ label }}</span>
          <strong class="mt-1 block text-base text-text">{{ value }}</strong>
        </article>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2 text-sm text-text-soft">
        <p>
          {{ klineLoading ? '正在加载最新 K 线...' : klineError ? klineError : '主图优先展示价格行为，新闻事件作为辅助证据层。' }}
        </p>
        <span class="text-[11px] uppercase tracking-[0.16em] text-text-faint">Updated {{ updatedAt }}</span>
      </div>
    </header>

    <section data-role="trading-desk-main">
      <KlineChart :kline-data="klineData" :highlighted-event-time="highlightedEventTime" @focus-news="focusNewsEvent" />
    </section>

    <section class="grid gap-4" data-role="watchlist-detail-news">
      <RelatedNewsSidebar :items="detailNews" :highlighted-event-time="highlightedEventTime" @focus-news="focusNewsItem" />
    </section>
  </section>
</template>
