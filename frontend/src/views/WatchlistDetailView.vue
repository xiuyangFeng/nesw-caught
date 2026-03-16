<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useWatchlistStore } from '../stores/watchlistStore';
import { formatNumber, formatPercent } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

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
  <div class="page">
    <header class="page-header">
      <div>
        <button class="back-link" type="button" @click="router.push('/watchlist')">返回自选股总览</button>
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
      <section class="detail-grid">
        <SectionCard title="核心行情" subtitle="最新价格、涨跌和数据状态">
          <div class="metric-stack">
            <div class="hero-price">
              <strong>{{ formatNumber(detailQuote?.price) }}</strong>
              <span :class="{ positive: (detailQuote?.change_percent ?? 0) > 0, negative: (detailQuote?.change_percent ?? 0) < 0 }">
                {{ formatNumber(detailQuote?.change_amount) }} / {{ formatPercent(detailQuote?.change_percent) }}
              </span>
            </div>
            <div class="status-line">
              <span class="pill" :class="detailQuote?.status === 'ok' ? 'positive' : 'negative'">{{ detailQuote?.status ?? '--' }}</span>
              <span>{{ detailQuote?.source ?? '--' }}</span>
            </div>
            <p v-if="detailQuote?.message" class="muted-text">{{ detailQuote.message }}</p>
          </div>
        </SectionCard>

        <SectionCard title="指标详情" subtitle="开盘、昨收、最高、最低、成交量">
          <div class="metrics-grid">
            <article>
              <span>开盘价</span>
              <strong>{{ formatNumber(detailQuote?.open_price) }}</strong>
            </article>
            <article>
              <span>昨收价</span>
              <strong>{{ formatNumber(detailQuote?.previous_close) }}</strong>
            </article>
            <article>
              <span>日内最高</span>
              <strong>{{ formatNumber(detailQuote?.day_high) }}</strong>
            </article>
            <article>
              <span>日内最低</span>
              <strong>{{ formatNumber(detailQuote?.day_low) }}</strong>
            </article>
            <article>
              <span>成交量</span>
              <strong>{{ formatNumber(detailQuote?.volume, 0) }}</strong>
            </article>
            <article>
              <span>更新时间</span>
              <strong>
                {{
                  detailQuote?.fetched_at
                    ? `${formatMarketTime(detailQuote.fetched_at, detailQuote.market)} ${getMarketTimezoneLabel(detailQuote.market)}`
                    : '--'
                }}
              </strong>
            </article>
          </div>
        </SectionCard>

        <SectionCard title="关联新闻" subtitle="继续沿用股票相关新闻命中结果">
          <LoadingBlock :loading="watchlistStore.relatedLoading" :empty="relatedNews.length === 0" empty-text="当前股票暂无关联新闻">
            <div class="related-list">
              <article v-for="item in relatedNews" :key="item.id" class="related-card">
                <div class="related-head">
                  <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                  <span>{{ item.source_name }}</span>
                </div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.summary }}</p>
                <span class="muted-text">
                  {{ formatMarketTime(item.published_at, item.market) }} {{ getMarketTimezoneLabel(item.market) }}
                </span>
              </article>
            </div>
          </LoadingBlock>
        </SectionCard>
      </section>
    </LoadingBlock>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.back-link {
  border: none;
  padding: 0;
  background: none;
  color: var(--accent);
  font: inherit;
  cursor: pointer;
}

.detail-grid {
  display: grid;
  gap: 16px;
}

.metric-stack,
.metrics-grid,
.related-list {
  display: grid;
  gap: 12px;
}

.hero-price strong {
  display: block;
  font-size: 40px;
  line-height: 1;
}

.status-line {
  display: flex;
  gap: 8px;
  align-items: center;
}

.metrics-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.metrics-grid article,
.related-card {
  border-radius: 18px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border);
}

.metrics-grid span,
.muted-text,
.related-head,
.related-card p {
  color: var(--muted);
}

.positive {
  color: var(--positive);
}

.negative {
  color: var(--negative);
}

.related-head {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
}
</style>
