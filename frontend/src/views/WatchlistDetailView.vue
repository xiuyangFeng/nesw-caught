<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import StockDetailPanel from '../components/watchlist/StockDetailPanel.vue';
import { HttpError } from '../api/http';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useWatchlistStore } from '../stores/watchlistStore';

const route = useRoute();
const router = useRouter();
const watchlistStore = useWatchlistStore();

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase());
const detailQuote = computed(() => watchlistStore.quoteDetail);

async function loadPageData(targetSymbol: string) {
  if (!targetSymbol) {
    await router.push({ name: 'watchlist' });
    return;
  }
  try {
    await watchlistStore.loadDetailWorkspace(targetSymbol);
  } catch (error) {
    if (error instanceof HttpError && error.status === 404) {
      await router.push({ name: 'watchlist' });
    }
    return;
  }
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
  <div class="grid gap-4" data-role="watchlist-detail-main">
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
      <StockDetailPanel
        :quote="detailQuote"
        :kline-data="watchlistStore.klineData"
        :detail-news="watchlistStore.detailNews"
        :research-brief="watchlistStore.researchBrief"
        :current-period="watchlistStore.currentPeriod"
        :kline-loading="watchlistStore.klineLoading"
        :kline-error="watchlistStore.klineError"
        @switch-period="watchlistStore.switchPeriod"
      />
    </LoadingBlock>
  </div>
</template>
