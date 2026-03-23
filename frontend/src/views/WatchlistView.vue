<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import WatchlistTable from '../components/watchlist/WatchlistTable.vue';
import { useRuntimeStatusStore } from '../stores/runtimeStatusStore';
import { useWatchlistStore } from '../stores/watchlistStore';
import type { WatchlistCandidate } from '../types/api';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const router = useRouter();
const runtimeStatusStore = useRuntimeStatusStore();
const watchlistStore = useWatchlistStore();
const selectedCandidate = ref<WatchlistCandidate | null>(null);
const form = reactive({
  query: '',
  alert_threshold: '',
});

const watchlistRows = computed(() => watchlistStore.quotes);
const abnormalMovers = computed(() => watchlistStore.quotes.filter((item) => item.is_abnormal));
const marketWorkerStatus = computed(() => runtimeStatusStore.marketWorkerStatus);
const normalizedQuery = computed(() => form.query.trim().toLowerCase());
const addedSymbols = computed(() => new Set(watchlistStore.items.map((item) => item.symbol)));

const filteredCandidates = computed(() => {
  if (!normalizedQuery.value) {
    return [];
  }

  return watchlistStore.candidates
    .filter((candidate) => {
      const haystack = [candidate.symbol, candidate.display_name, ...(candidate.aliases ?? [])]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery.value);
    })
    .slice(0, 8);
});

const relatedNews = computed(() => {
  const symbol = watchlistStore.selectedSymbol;
  return symbol ? watchlistStore.relatedNews[symbol] ?? [] : [];
});
const lastManualRefreshResult = computed(() => watchlistStore.lastManualRefreshResult);

async function selectSymbol(symbol: string) {
  await watchlistStore.loadRelatedNews(symbol);
  await router.push(`/watchlist/${encodeURIComponent(symbol)}`);
}

function selectCandidate(candidate: WatchlistCandidate) {
  selectedCandidate.value = candidate;
  form.query = `${candidate.display_name} · ${candidate.symbol}`;
}

function isCandidateAdded(symbol: string) {
  return addedSymbols.value.has(symbol);
}

async function submitWatchlist() {
  if (!selectedCandidate.value) {
    watchlistStore.createError = '请先从候选列表中选择一只股票';
    return;
  }

  try {
    await watchlistStore.createWatchlist({
      symbol: selectedCandidate.value.symbol,
      market: selectedCandidate.value.market,
      display_name: selectedCandidate.value.display_name,
      alert_threshold: form.alert_threshold ? Number(form.alert_threshold) : null,
      alert_mode: 'fixed',
    });
    form.query = '';
    form.alert_threshold = '';
    selectedCandidate.value = null;
  } catch {
    // Error state is handled by the store for inline display.
  }
}

async function handleDelete(symbol: string) {
  if (!window.confirm(`确认删除 ${symbol} 吗？`)) {
    return;
  }

  try {
    await watchlistStore.deleteWatchlist(symbol);
    if (watchlistStore.selectedSymbol) {
      await watchlistStore.loadRelatedNews(watchlistStore.selectedSymbol);
    }
  } catch {
    // Error state is handled by the store for inline display.
  }
}

async function handleManualRefresh() {
  try {
    await watchlistStore.refreshMarketQuotes();
    if (watchlistStore.selectedSymbol) {
      await watchlistStore.loadRelatedNews(watchlistStore.selectedSymbol);
    }
  } catch {
    // Error state is handled by the store for inline display.
  }
}

onMounted(async () => {
  try {
    await watchlistStore.loadCandidates();
  } catch {
    // Candidate load errors are surfaced inline; keep the page usable.
  }
  if (!watchlistStore.items.length) {
    await watchlistStore.loadWatchlist();
  }
  if (watchlistStore.selectedSymbol) {
    await watchlistStore.loadRelatedNews(watchlistStore.selectedSymbol);
  }
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">Watchlist</h1>
        <p class="page-subtitle">批量查看自选股实时行情，点击股票进入详情页查看更多指标和相关新闻。</p>
      </div>
      <StaleBadge :stale="watchlistStore.stale" label="自选股与行情" />
    </header>

    <StatusBanner
      :title="abnormalMovers.length ? '检测到自选股异动' : '当前没有明显异动'"
      :tone="abnormalMovers.length ? 'warning' : 'default'"
      detail="列表展示价格、涨跌、开盘、昨收、最高、最低和成交量。"
    />

    <section
      class="grid gap-2 rounded-[18px] border border-[rgba(148,163,184,0.14)] bg-[linear-gradient(135deg,rgba(12,19,31,0.94),rgba(8,14,24,0.98))] px-4 py-3 text-sm shadow-[0_16px_36px_rgba(2,6,12,0.22)]"
      data-role="market-worker-status"
    >
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Market Worker</span>
        <strong class="text-text">{{ marketWorkerStatus?.name ?? 'market_quote_producer' }}</strong>
        <span
          class="rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-[0.18em]"
          :class="
            marketWorkerStatus?.status === 'ok'
              ? 'border-[rgba(74,222,128,0.28)] text-[rgba(134,239,172,0.94)]'
              : marketWorkerStatus?.status === 'degraded'
                ? 'border-[rgba(248,113,113,0.28)] text-[rgba(252,165,165,0.94)]'
                : 'border-border text-text-faint'
          "
        >
          {{ marketWorkerStatus?.status ?? 'unknown' }}
        </span>
        <span class="text-text-faint">
          最近产出 {{ marketWorkerStatus?.last_quotes_count ?? 0 }} 条行情
        </span>
        <button
          class="rounded-full border border-[#ff9f2f33] bg-[rgba(255,159,47,0.08)] px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-[#ffca97] transition hover:bg-[rgba(255,159,47,0.14)] disabled:cursor-progress disabled:opacity-60"
          :disabled="watchlistStore.refreshLoading"
          data-role="market-refresh-action"
          @click="handleManualRefresh"
        >
          {{ watchlistStore.refreshLoading ? '刷新中...' : '立即刷新一轮' }}
        </button>
      </div>
      <p class="m-0 text-text-soft">
        最近成功：
        {{ marketWorkerStatus?.last_success_at ? formatMarketTime(marketWorkerStatus.last_success_at, 'us') : '暂无记录' }}
      </p>
      <p v-if="marketWorkerStatus?.last_error" class="m-0 text-negative">
        最近错误：{{ marketWorkerStatus.last_error }}
      </p>
      <p v-if="lastManualRefreshResult" class="m-0 text-text-soft">
        最近手动刷新：{{ formatMarketTime(lastManualRefreshResult.triggered_at, 'us') }}，刷新了
        {{ lastManualRefreshResult.quotes_count }} 个标的
        <span v-if="lastManualRefreshResult.symbols.length">
          （{{ lastManualRefreshResult.symbols.join(', ') }}）
        </span>
      </p>
      <p v-if="watchlistStore.refreshError" class="m-0 text-negative">
        {{ watchlistStore.refreshError }}
      </p>
    </section>

    <section class="grid gap-4 xl:grid-cols-[1.5fr_0.9fr]" data-role="watchlist-layout">
      <SectionCard
        title="管理自选股"
        subtitle="输入名称或代码片段即可联想候选，添加与删除都在同一块面板完成"
        data-role="watchlist-shell"
      >
        <p class="mb-3 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Control Station</p>
        <form class="mb-[14px] grid gap-3" @submit.prevent="submitWatchlist">
          <label class="relative grid gap-1.5 text-sm text-text-faint">
            <span>搜索股票</span>
            <input
              v-model.trim="form.query"
              class="rounded-xl border border-border bg-field px-3 py-2.5 text-text"
              placeholder="输入股票代码、中文名或英文名"
            />
            <div
              v-if="filteredCandidates.length"
              class="mt-1.5 grid gap-2 rounded-2xl border border-border bg-[rgba(8,15,28,0.94)] p-2.5"
              data-role="candidate-list"
            >
              <button
                v-for="candidate in filteredCandidates"
                :key="candidate.symbol"
                class="flex w-full items-center justify-between gap-3 rounded-[14px] border border-[rgba(148,163,184,0.12)] bg-[rgba(15,23,42,0.72)] p-3 text-left text-text disabled:cursor-not-allowed disabled:opacity-70"
                type="button"
                :disabled="isCandidateAdded(candidate.symbol)"
                @click="selectCandidate(candidate)"
              >
                <span class="grid gap-1">
                  <strong>{{ candidate.display_name }}</strong>
                  <small class="text-text-faint">{{ candidate.symbol }} · {{ candidate.market.toUpperCase() }}</small>
                </span>
                <span class="text-text-faint">{{ isCandidateAdded(candidate.symbol) ? '已添加' : '选择' }}</span>
              </button>
            </div>
          </label>

          <label class="grid gap-1.5 text-sm text-text-faint">
            <span>阈值（可选）</span>
            <input
              v-model.trim="form.alert_threshold"
              class="rounded-xl border border-border bg-field px-3 py-2.5 text-text"
              type="number"
              min="0"
              step="0.1"
              placeholder="例如 3"
            />
          </label>

          <button
            class="rounded-full border border-[#ff9f2f4f] bg-[linear-gradient(135deg,#9b5718,#ff9f2f)] px-4 py-3 font-semibold text-[#2f1500] transition duration-150 ease-out hover:-translate-y-px hover:shadow-[0_10px_24px_rgba(255,159,47,0.22)] disabled:cursor-progress disabled:opacity-60 disabled:shadow-none"
            type="submit"
            :disabled="watchlistStore.createLoading || !selectedCandidate"
            data-role="watchlist-action"
          >
            {{ watchlistStore.createLoading ? '提交中...' : '添加到自选股' }}
          </button>

          <p v-if="selectedCandidate" class="m-0 text-text-soft">
            已选择 {{ selectedCandidate.display_name }} · {{ selectedCandidate.symbol }}
          </p>
          <p v-if="watchlistStore.createError" class="m-0 text-negative">{{ watchlistStore.createError }}</p>
          <p v-if="watchlistStore.deleteError" class="m-0 text-negative">{{ watchlistStore.deleteError }}</p>
          <p v-if="watchlistStore.candidateError" class="m-0 text-negative">{{ watchlistStore.candidateError }}</p>
        </form>

        <LoadingBlock :loading="watchlistStore.loading" :empty="watchlistRows.length === 0">
          <WatchlistTable
            :rows="watchlistRows"
            :selected-symbol="watchlistStore.selectedSymbol"
            :deleting-symbol="watchlistStore.deleteLoadingSymbol"
            @select="selectSymbol"
            @delete="handleDelete"
          />
        </LoadingBlock>
      </SectionCard>

      <SectionCard
        title="关联新闻"
        subtitle="这里保留为快速预览，完整行情指标请进入单股详情页查看"
        data-role="related-news-shell"
      >
        <LoadingBlock
          :loading="watchlistStore.relatedLoading"
          :empty="!watchlistStore.selectedSymbol || relatedNews.length === 0"
          empty-text="当前股票暂无关联新闻"
        >
          <div class="grid gap-3">
            <article
              v-for="item in relatedNews"
              :key="item.id"
              class="rounded-[14px] border border-border/90 bg-[linear-gradient(180deg,rgba(11,18,28,0.98),rgba(8,14,23,0.98))] p-4 shadow-[0_14px_30px_rgba(2,6,12,0.24)] transition duration-150 ease-out hover:-translate-y-px hover:border-[#ff9f2f4f]"
            >
              <div class="mb-2 flex gap-2 text-text-faint">
                <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                <span>{{ item.source_name }}</span>
              </div>
              <strong>{{ item.title }}</strong>
              <p class="text-text-soft">{{ item.summary }}</p>
              <span class="text-text-faint">
                {{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}
              </span>
            </article>
          </div>
        </LoadingBlock>
      </SectionCard>
    </section>
  </div>
</template>
