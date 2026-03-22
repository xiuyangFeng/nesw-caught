<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useWatchlistStore } from '../stores/watchlistStore';
import { formatNumber, formatPercent } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const watchlistStore = useWatchlistStore();

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase());
const detailQuote = computed(() => watchlistStore.quoteDetail);
const relatedNews = computed(() => watchlistStore.relatedNews[symbol.value] ?? []);

async function loadPageData(targetSymbol: string) {
  if (!targetSymbol) {
    return;
  }
  await Promise.all([
    watchlistStore.loadQuoteDetail(targetSymbol),
    watchlistStore.loadRelatedNews(targetSymbol),
  ]);
}

onMounted(async () => {
  await loadPageData(symbol.value);
});

watch(symbol, async (nextSymbol, previousSymbol) => {
  if (nextSymbol && nextSymbol !== previousSymbol) {
    await loadPageData(nextSymbol);
  }
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <button class="border-none bg-transparent p-0 text-accent" type="button" @click="router.push('/watchlist')">
          返回自选股总览
        </button>
        <h1 class="page-title">{{ detailQuote?.display_name ?? symbol }}</h1>
        <p class="page-subtitle">
          {{ detailQuote?.symbol ?? symbol }}
          <template v-if="detailQuote?.market"> · {{ detailQuote.market.toUpperCase() }}</template>
          <template v-if="detailQuote?.provider_symbol"> · {{ detailQuote.provider_symbol }}</template>
        </p>
      </div>
      <StaleBadge :stale="watchlistStore.stale" label="单股行情" />
    </header>

    <LoadingBlock :loading="watchlistStore.detailLoading" :empty="!detailQuote" empty-text="当前股票暂无可用行情">
      <section class="grid gap-4" data-role="watchlist-detail-grid">
        <SectionCard title="核心行情" subtitle="最新价格、涨跌和数据状态">
          <div
            class="grid gap-3 rounded-[16px] border border-[#ff9f2f33] bg-[linear-gradient(160deg,rgba(19,26,37,0.96),rgba(8,16,26,0.98))] px-4 py-4"
            data-role="watchlist-detail-hero"
          >
            <div>
              <strong class="block text-[40px] leading-none">{{ formatNumber(detailQuote?.price) }}</strong>
              <span
                :class="
                  (detailQuote?.change_percent ?? 0) > 0
                    ? 'text-positive'
                    : (detailQuote?.change_percent ?? 0) < 0
                      ? 'text-negative'
                      : 'text-text'
                "
                data-role="price-change"
              >
                {{ formatNumber(detailQuote?.change_amount) }} / {{ formatPercent(detailQuote?.change_percent) }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="pill" :class="detailQuote?.status === 'ok' ? 'positive' : 'negative'">{{ detailQuote?.status ?? '--' }}</span>
              <span>{{ detailQuote?.source ?? '--' }}</span>
            </div>
            <p v-if="detailQuote?.message" class="text-text-faint">{{ detailQuote.message }}</p>
          </div>
        </SectionCard>

        <SectionCard title="指标详情" subtitle="开盘、昨收、最高、最低、成交量">
          <div class="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
            <article
              v-for="metric in [
                ['开盘价', formatNumber(detailQuote?.open_price)],
                ['昨收价', formatNumber(detailQuote?.previous_close)],
                ['日内最高', formatNumber(detailQuote?.day_high)],
                ['日内最低', formatNumber(detailQuote?.day_low)],
                ['成交量', formatNumber(detailQuote?.volume, 0)],
                [
                  '更新时间',
                  detailQuote?.fetched_at
                    ? `${formatMarketTime(detailQuote.fetched_at, detailQuote.market)} ${getMarketTimezoneLabel(detailQuote.market)}`
                    : '--',
                ],
              ]"
              :key="metric[0]"
              class="terminal-surface rounded-[18px] border border-border p-4 transition duration-150 ease-out hover:-translate-y-px hover:border-system/20 hover:shadow-[0_14px_28px_rgba(2,6,12,0.2)]"
              data-surface="terminal-metric-card"
            >
              <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ metric[0] }}</span>
              <strong class="text-text">{{ metric[1] }}</strong>
            </article>
          </div>
        </SectionCard>

        <SectionCard title="关联新闻" subtitle="继续沿用股票相关新闻命中结果">
          <LoadingBlock :loading="watchlistStore.relatedLoading" :empty="relatedNews.length === 0" empty-text="当前股票暂无关联新闻">
            <div class="grid gap-3">
              <article
              v-for="item in relatedNews"
              :key="item.id"
              class="terminal-surface rounded-[14px] border border-border p-4 transition duration-150 ease-out hover:-translate-y-px hover:border-[#ff9f2f4f] hover:shadow-[0_14px_28px_rgba(2,6,12,0.2)]"
              data-surface="terminal-related-card"
            >
                <div class="mb-2 flex gap-2 text-xs text-text-faint">
                  <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                  <span>{{ item.source_name }}</span>
                </div>
                <strong class="text-text">{{ item.title }}</strong>
                <p class="text-text-soft">{{ item.summary }}</p>
                <span class="text-text-faint">
                  {{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}
                </span>
              </article>
            </div>
          </LoadingBlock>
        </SectionCard>
      </section>
    </LoadingBlock>
  </div>
</template>
