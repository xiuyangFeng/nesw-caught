<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import KlineChart from '../components/watchlist/KlineChart.vue';
import FundFlowPanel from '../components/watchlist/FundFlowPanel.vue';
import { apiClient } from '../api/client';
import type { QuantResearchPack, StockKlineResponse, WatchlistDashboardPeriod } from '../types/api';

// 与 watchlistStore 的 PERIOD_QUERY_MAP 保持一致，避免 interval/range 取值分叉。
const PERIOD_QUERY_MAP: Record<WatchlistDashboardPeriod, { interval: string; range: string }> = {
  '1D': { interval: '1d', range: '1y' },
  '1W': { interval: '1wk', range: '5y' },
  '1M': { interval: '1mo', range: '10y' },
  '1Y': { interval: '1mo', range: 'max' },
};

const route = useRoute();
const router = useRouter();
const pack = ref<QuantResearchPack | null>(null);
const error = ref<string | null>(null);

const klineData = ref<StockKlineResponse | null>(null);
const klineLoading = ref(false);
const klineError = ref<string | null>(null);
const currentPeriod = ref<WatchlistDashboardPeriod>('1D');

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase());
const isAShare = computed(() => /\.(SH|SZ|BJ)$/.test(symbol.value));

async function load() {
  if (!symbol.value) return;
  try {
    const response = await apiClient.getQuantResearch(symbol.value);
    pack.value = response.data;
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '研究包加载失败';
  }
}

async function loadKline(period: WatchlistDashboardPeriod = currentPeriod.value) {
  if (!symbol.value) return;
  const query = PERIOD_QUERY_MAP[period];
  currentPeriod.value = period;
  klineLoading.value = true;
  klineError.value = null;
  try {
    const response = await apiClient.getStockKline(symbol.value, query.interval, query.range);
    klineData.value = response.data;
  } catch {
    // 与 watchlistStore.loadKline 一致：不回显原始错误文本，统一给简洁空态文案。
    klineData.value = null;
    klineError.value = 'K 线数据加载失败，请稍后重试';
  } finally {
    klineLoading.value = false;
  }
}

function switchPeriod(period: WatchlistDashboardPeriod) {
  void loadKline(period);
}

function askAi() {
  void router.push({ path: '/chat', query: { desk_symbol: symbol.value } });
}

onMounted(() => {
  void load();
  void loadKline();
});

watch(symbol, () => {
  void load();
  void loadKline(currentPeriod.value);
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-stock-view">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="page-title">个股研究 {{ symbol }}</h1>
        <p class="page-subtitle">纵横研究包回答必答问题；缺财务时显式缺口，不编造数字。</p>
      </div>
      <button
        type="button"
        class="rounded-md px-3 py-1.5 text-sm text-white"
        style="background: #8b7cff"
        data-role="desk-ask-ai"
        @click="askAi"
      >
        问 AI
      </button>
    </header>
    <SectionCard eyebrow="Kline" title="K 线图" subtitle="日K/周K/月K/年K；数据来自行情接口，加载失败不影响下方研究包">
      <KlineChart
        v-if="klineData"
        :kline-data="klineData"
        :current-period="currentPeriod"
        @switch-period="switchPeriod"
      />
      <p v-else-if="klineLoading" class="text-sm text-muted" data-role="desk-kline-loading">正在加载 K 线…</p>
      <p v-else class="text-sm text-muted" data-role="desk-kline-empty">{{ klineError ?? '暂无 K 线数据' }}</p>
    </SectionCard>

    <FundFlowPanel v-if="isAShare" :symbol="symbol" />

    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard
      v-for="module in pack?.modules ?? []"
      :key="module.key"
      :eyebrow="module.key"
      :title="module.question"
    >
      <p class="text-sm text-text">{{ module.answer }}</p>
      <p v-if="module.gap" class="mt-2 text-xs text-warning">缺口：{{ module.gap }}</p>
      <p v-if="module.evidence_ids?.length" class="mt-2 text-xs text-muted">证据 {{ module.evidence_ids.join(', ') }}</p>
    </SectionCard>
    <p class="text-xs text-muted">副驾工具白名单只读：资金流、研究包、新闻检索、策略预览、回测报告、成绩单。不能下单或改策略。</p>
  </div>
</template>
