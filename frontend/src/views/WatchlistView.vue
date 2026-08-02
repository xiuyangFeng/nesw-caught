<script setup lang="ts">
import { computed, onMounted, onUnmounted, provide, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import StaleBadge from '../components/common/StaleBadge.vue';
import SectionCard from '../components/common/SectionCard.vue';
import MarketOverviewPanel from '../components/watchlist/MarketOverviewPanel.vue';
import WatchlistAddModal from '../components/watchlist/WatchlistAddModal.vue';
import WatchlistSidebar from '../components/watchlist/WatchlistSidebar.vue';
import LoadingBlock from '../components/common/LoadingBlock.vue';
import { useMarketOverviewStore } from '../stores/marketOverviewStore';
import { useRuntimeStatusStore } from '../stores/runtimeStatusStore';
import { useWatchlistStore } from '../stores/watchlistStore';
import type { PortfolioSummary, WatchlistCandidate } from '../types/api';
import { getRuntimeDiagnostic } from '../utils/runtimeDiagnostics';
import { formatNumber, formatPercent, sentimentText } from '../utils/format';
import { formatMarketTime } from '../utils/time';
import { logger } from '../utils/logger';
import { apiClient } from '../api/client';

const route = useRoute();
const router = useRouter();
const runtimeStatusStore = useRuntimeStatusStore();
const watchlistStore = useWatchlistStore();
const marketOverviewStore = useMarketOverviewStore();

const isAddModalOpen = ref(false);
const addModalQuery = ref('');
const addModalSelectedCandidate = ref<WatchlistCandidate | null>(null);
const addModalAdvancedOpen = ref(false);
const addModalAlertThreshold = ref('');

const dynamicMatches = ref<WatchlistCandidate[]>([]);
const isSearching = ref(false);
let searchDebounceTimer: any = null;

// Tab 切换：quotes(自选行情) | portfolio(持仓组合) | news(重磅持仓新闻)
const activeTab = ref<'quotes' | 'portfolio' | 'news'>('quotes');

// 从 URL Query 中同步 activeTab (支持 /watchlist?tab=portfolio)
watch(
  () => route?.query?.tab,
  (tabVal) => {
    if (tabVal === 'portfolio' || tabVal === 'news') {
      activeTab.value = tabVal;
    } else {
      activeTab.value = 'quotes';
    }
  },
  { immediate: true },
);

function switchTab(tab: 'quotes' | 'portfolio' | 'news') {
  activeTab.value = tab;
  router.replace({ query: { ...route.query, tab: tab === 'quotes' ? undefined : tab } });
}

// 组合数据状态
const portfolioSummary = ref<PortfolioSummary | null>(null);
const portfolioLoading = ref(false);
const portfolioError = ref<string | null>(null);

const hasHoldings = computed(() => (portfolioSummary.value?.positions.length ?? 0) > 0);

async function loadPortfolio() {
  portfolioLoading.value = true;
  portfolioError.value = null;
  try {
    const response = await apiClient.getPortfolio();
    portfolioSummary.value = response.data;
  } catch {
    portfolioError.value = '组合数据加载失败，请稍后重试';
  } finally {
    portfolioLoading.value = false;
  }
}

// 持仓/组合视图：为每只自选股就地编辑「持仓量 / 成本」。
const positionDrafts = ref<Record<string, { position_size: string; average_cost: string }>>({});
const savingSymbol = ref<string | null>(null);
const positionError = ref<string | null>(null);

function syncPositionDrafts() {
  const next: Record<string, { position_size: string; average_cost: string }> = {};
  for (const item of watchlistStore.items) {
    next[item.symbol] = {
      position_size: item.position_size !== null && item.position_size !== undefined ? String(item.position_size) : '',
      average_cost: item.average_cost !== null && item.average_cost !== undefined ? String(item.average_cost) : '',
    };
  }
  positionDrafts.value = next;
}

watch(() => watchlistStore.items, syncPositionDrafts, { immediate: true });

function toNonNegativeNumberOrNull(raw: unknown): number | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  if (typeof raw === 'number') {
    return Number.isFinite(raw) && raw >= 0 ? raw : null;
  }
  const str = String(raw).trim();
  if (!str) {
    return null;
  }
  const value = Number(str);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

const positionSuccessMessage = ref<string | null>(null);

async function savePosition(symbol: string) {
  const draft = positionDrafts.value[symbol];
  if (!draft) {
    return;
  }
  savingSymbol.value = symbol;
  positionError.value = null;
  positionSuccessMessage.value = null;
  try {
    const res = await apiClient.setWatchlistPosition(symbol, {
      position_size: toNonNegativeNumberOrNull(draft.position_size),
      average_cost: toNonNegativeNumberOrNull(draft.average_cost),
    });

    if (res.data) {
      positionDrafts.value[symbol] = {
        position_size: res.data.position_size !== null && res.data.position_size !== undefined ? String(res.data.position_size) : '',
        average_cost: res.data.average_cost !== null && res.data.average_cost !== undefined ? String(res.data.average_cost) : '',
      };
    }

    await watchlistStore.loadWatchlist();
    await loadPortfolio();

    positionSuccessMessage.value = `${symbol} 持仓保存成功`;
    setTimeout(() => {
      if (positionSuccessMessage.value === `${symbol} 持仓保存成功`) {
        positionSuccessMessage.value = null;
      }
    }, 2500);
  } catch (err: unknown) {
    const detail = err instanceof Error ? err.message : '请稍后重试';
    positionError.value = `保存 ${symbol} 持仓失败: ${detail}`;
  } finally {
    savingSymbol.value = null;
  }
}

// 辅助函数
function pnlToneClass(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return 'text-muted';
  }
  return value >= 0 ? 'text-success' : 'text-danger';
}

function formatSignedMoney(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '--';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatNumber(value)}`;
}

function weightLabel(weight: number | null | undefined) {
  if (weight === null || weight === undefined) {
    return '--';
  }
  return `${(weight * 100).toFixed(1)}%`;
}

// 自选股卡片“距财报 N 天”角标数据
const earningsCountdown = ref<Record<string, number>>({});
provide('watchlistEarningsCountdown', earningsCountdown);

async function loadEarningsCountdown() {
  try {
    const { data } = await apiClient.getCalendar(90);
    const nextMap: Record<string, number> = {};
    for (const summary of data.summaries ?? []) {
      if (summary.next_earnings_days_until !== null && summary.next_earnings_days_until !== undefined) {
        nextMap[summary.symbol] = summary.next_earnings_days_until;
      }
    }
    earningsCountdown.value = nextMap;
  } catch {
    // 静默降级
  }
}

function performSearch(queryText: string) {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  const trimmed = queryText.trim();
  if (!trimmed) {
    dynamicMatches.value = [];
    return;
  }
  isSearching.value = true;
  const isTest = typeof process !== 'undefined' && process.env?.NODE_ENV === 'test';
  const debounceMs = isTest ? 0 : 100;
  searchDebounceTimer = setTimeout(async () => {
    try {
      const res = await apiClient.searchMarketSymbols(trimmed);
      dynamicMatches.value = res.data;
    } catch (err) {
      logger.error('Failed to search market symbols', err);
    } finally {
      isSearching.value = false;
    }
  }, debounceMs);
}

watch(addModalQuery, (newVal) => {
  performSearch(newVal);
});

const addModalMatches = computed(() => {
  const keyword = addModalQuery.value.trim().toLowerCase();
  if (!keyword) {
    return watchlistStore.candidates;
  }
  return dynamicMatches.value;
});

function openAddModal() {
  watchlistStore.createError = null;
  isAddModalOpen.value = true;
}

function closeAddModal() {
  watchlistStore.createError = null;
  isAddModalOpen.value = false;
  addModalQuery.value = '';
  addModalSelectedCandidate.value = null;
  addModalAdvancedOpen.value = false;
  addModalAlertThreshold.value = '';
}

function handleSelectAddCandidate(candidate: WatchlistCandidate) {
  addModalSelectedCandidate.value = candidate;
}

function handleSelectSymbol(symbol: string) {
  router.push({ name: 'watchlist-detail', params: { symbol } });
}

async function handleAddCandidate() {
  if (!addModalSelectedCandidate.value) {
    return;
  }

  const threshold = addModalAlertThreshold.value.trim();
  try {
    await watchlistStore.createWatchlist({
      symbol: addModalSelectedCandidate.value.symbol,
      market: addModalSelectedCandidate.value.market,
      display_name: addModalSelectedCandidate.value.display_name,
      alert_threshold: addModalAdvancedOpen.value && threshold ? Number(threshold) : null,
      alert_mode: 'fixed',
    });
    await router.push({ name: 'watchlist-detail', params: { symbol: addModalSelectedCandidate.value.symbol } });
    closeAddModal();
  } catch {
  }
}

async function handleDeleteSymbol(symbol: string) {
  if (!window.confirm(`确认删除 ${symbol} 吗？`)) {
    return;
  }
  try {
    await watchlistStore.deleteWatchlist(symbol);
    await loadPortfolio();
  } catch {
  }
}

async function handleManualRefresh() {
  try {
    await watchlistStore.refreshMarketQuotes();
    await loadPortfolio();
  } catch {
  }
}

const runtimeDiagnostic = computed(() =>
  getRuntimeDiagnostic({
    connectionState: 'live',
    streamStatus: runtimeStatusStore.streamStatus ?? null,
    usingMock: runtimeStatusStore.usingMock ?? false,
    marketWorkerStatus: runtimeStatusStore.marketWorkerStatus,
  }),
);

onMounted(async () => {
  // 市场总览:首次加载 + 60s 定时刷新(loadOverview 内部收敛错误,不会抛出)。
  void marketOverviewStore.loadOverview();
  marketOverviewStore.startAutoRefresh();
  try {
    await watchlistStore.loadCandidates();
  } catch {
  }
  await watchlistStore.loadWatchlist();
  await loadPortfolio();
  void loadEarningsCountdown();
});

onUnmounted(() => {
  marketOverviewStore.stopAutoRefresh();
});
</script>

<template>
  <div class="grid gap-4" data-role="watchlist-dashboard">
    <!-- 统一工作台页头 Header -->
    <header class="flex flex-col gap-4 rounded-lg border border-border bg-panel p-5 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-[11px] uppercase tracking-[0.24em] text-accent">Watchlist & Portfolio</span>
          <span class="rounded-full bg-accent/10 px-2.5 py-0.5 text-[10px] text-accent border border-accent/30">一体化工作台</span>
        </div>
        <h1 class="page-title mb-1.5 mt-1">自选股 & 组合持仓</h1>
        <p class="page-subtitle">监控股票行情、核算持仓实时盈亏，并一站式跟踪影响资金最多钱的重磅新闻。</p>
      </div>

      <!-- 组合盈亏即时摘要卡片 (Portfolio Snapshot) -->
      <div v-if="portfolioSummary && hasHoldings" class="flex flex-wrap items-center gap-4 rounded-xl border border-border/80 bg-black/20 p-3">
        <div class="grid gap-0.5">
          <span class="text-[10px] uppercase tracking-[0.14em] text-muted">组合总市值</span>
          <span class="font-mono text-base font-bold text-text">¥{{ formatNumber(portfolioSummary.total_market_value) }}</span>
        </div>
        <div class="h-8 w-px bg-border/60"></div>
        <div class="grid gap-0.5">
          <span class="text-[10px] uppercase tracking-[0.14em] text-muted">未实现盈亏</span>
          <span class="font-mono text-base font-bold" :class="pnlToneClass(portfolioSummary.total_unrealized_pnl)">
            {{ formatSignedMoney(portfolioSummary.total_unrealized_pnl) }} ({{ formatPercent(portfolioSummary.total_unrealized_pnl_percent) }})
          </span>
        </div>
        <div class="h-8 w-px bg-border/60"></div>
        <div class="grid gap-0.5">
          <span class="text-[10px] uppercase tracking-[0.14em] text-muted">持仓数</span>
          <span class="font-mono text-base font-bold text-text">{{ portfolioSummary.position_count }} 只</span>
        </div>
      </div>

      <StaleBadge :stale="watchlistStore.stale" label="行情列表" />
    </header>

    <!-- 市场总览区块(五市场指数/板块/情绪,Tab 切换之上) -->
    <MarketOverviewPanel />

    <!-- 视角 Tab 切换条 (Integrated View Tabs) -->
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border/80 pb-3" data-role="watchlist-tabs">
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-full px-4 py-1.5 text-xs font-semibold transition"
          :class="activeTab === 'quotes' ? 'bg-accent text-[var(--bg)] shadow-sm' : 'border border-border bg-panel text-text-soft hover:text-text'"
          data-role="tab-quotes"
          @click="switchTab('quotes')"
        >
          📈 自选行情 ({{ watchlistStore.items.length }})
        </button>
        <button
          type="button"
          class="rounded-full px-4 py-1.5 text-xs font-semibold transition"
          :class="activeTab === 'portfolio' ? 'bg-accent text-[var(--bg)] shadow-sm' : 'border border-border bg-panel text-text-soft hover:text-text'"
          data-role="tab-portfolio"
          @click="switchTab('portfolio')"
        >
          💼 组合持仓 ({{ portfolioSummary?.position_count ?? 0 }})
        </button>
        <button
          type="button"
          class="rounded-full px-4 py-1.5 text-xs font-semibold transition"
          :class="activeTab === 'news' ? 'bg-accent text-[var(--bg)] shadow-sm' : 'border border-border bg-panel text-text-soft hover:text-text'"
          data-role="tab-news"
          @click="switchTab('news')"
        >
          📰 持仓重磅新闻 ({{ portfolioSummary?.weighted_news.length ?? 0 }})
        </button>
      </div>

      <button
        type="button"
        class="rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-[var(--bg)] transition hover:brightness-110"
        data-role="watchlist-open-add-modal"
        @click="openAddModal"
      >
        添加
      </button>
    </div>

    <!-- 运行状态 Worker Bar -->
    <section class="grid gap-2 rounded-lg border border-border bg-panel px-4 py-3 text-sm" data-role="market-worker-status">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[11px] uppercase tracking-[0.24em] text-accent">Market Worker</span>
        <strong class="text-text">{{ runtimeStatusStore.marketWorkerStatus?.name ?? 'market_quote_producer' }}</strong>
        <span class="rounded-full border border-border px-2 py-0.5 text-[11px] uppercase tracking-[0.18em] text-text-faint">
          {{ runtimeStatusStore.marketWorkerStatus?.status ?? 'unknown' }}
        </span>
        <button
          class="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:bg-accent/20 disabled:cursor-progress disabled:opacity-60"
          :disabled="watchlistStore.refreshLoading"
          data-role="market-refresh-action"
          @click="handleManualRefresh"
        >
          {{ watchlistStore.refreshLoading ? '刷新中...' : '立即刷新一轮' }}
        </button>
      </div>
      <p class="m-0 text-text-soft" data-role="runtime-diagnostic-headline">{{ runtimeDiagnostic.headline }}</p>
      <p v-if="watchlistStore.lastManualRefreshResult" class="m-0 text-text-soft">
        最近手动刷新：{{ formatMarketTime(watchlistStore.lastManualRefreshResult.triggered_at, 'us') }}
      </p>
      <p v-if="watchlistStore.refreshError" class="m-0 text-danger">{{ watchlistStore.refreshError }}</p>
    </section>

    <!-- Tab 1: 自选行情视图 (Quotes) -->
    <section v-if="activeTab === 'quotes'">
      <LoadingBlock :loading="watchlistStore.loading" :empty="watchlistStore.items.length === 0" :skeletonType="'watchlist'" :skeletonCount="3">
        <WatchlistSidebar
          :items="watchlistStore.items"
          :quotes="watchlistStore.quotes"
          :selected-symbol="watchlistStore.selectedSymbol"
          :sparklines="watchlistStore.sparklines"
          :delete-error="watchlistStore.deleteError"
          :delete-loading-symbol="watchlistStore.deleteLoadingSymbol"
          @select="handleSelectSymbol"
          @open-add-modal="openAddModal"
          @delete="handleDeleteSymbol"
          @refresh="handleManualRefresh"
        />
      </LoadingBlock>

      <!-- 底部内嵌持仓快捷编辑区 -->
      <SectionCard
        v-if="watchlistStore.items.length > 0"
        class="mt-4"
        title="持仓设置"
        subtitle="填写持仓量与成本后，可实时查看持仓组合盈亏与按仓位加权的新闻"
        eyebrow="Positions"
        data-role="watchlist-position-panel"
      >
        <p v-if="positionError" class="mb-2 text-sm text-danger">{{ positionError }}</p>
        <p v-if="positionSuccessMessage" class="mb-2 text-sm text-success">{{ positionSuccessMessage }}</p>
        <div class="grid gap-2">
          <div
            v-for="item in watchlistStore.items"
            v-show="positionDrafts[item.symbol]"
            :key="item.symbol"
            class="grid gap-3 rounded-[14px] border border-border bg-white/[0.02] p-3 sm:grid-cols-[minmax(0,1fr)_auto_auto_auto] sm:items-end"
            data-role="watchlist-position-editor"
          >
            <div class="grid gap-0.5">
              <span class="font-mono text-[13px] text-text">{{ item.symbol }}</span>
              <span class="text-[11px] text-muted">{{ item.display_name }}</span>
            </div>
            <label class="grid gap-1 text-[11px] uppercase tracking-[0.12em] text-muted">
              持仓量
              <input
                v-if="positionDrafts[item.symbol]"
                v-model="positionDrafts[item.symbol].position_size"
                type="number"
                min="0"
                step="any"
                inputmode="decimal"
                placeholder="--"
                class="w-32 rounded-[10px] border border-border bg-black/20 px-2.5 py-1.5 text-sm text-text outline-none focus:border-system/40"
                data-role="position-size-input"
              />
            </label>
            <label class="grid gap-1 text-[11px] uppercase tracking-[0.12em] text-muted">
              成本价
              <input
                v-if="positionDrafts[item.symbol]"
                v-model="positionDrafts[item.symbol].average_cost"
                type="number"
                min="0"
                step="any"
                inputmode="decimal"
                placeholder="--"
                class="w-32 rounded-[10px] border border-border bg-black/20 px-2.5 py-1.5 text-sm text-text outline-none focus:border-system/40"
                data-role="average-cost-input"
              />
            </label>
            <button
              type="button"
              class="h-fit rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:bg-accent/20 disabled:cursor-progress disabled:opacity-60"
              :disabled="savingSymbol === item.symbol"
              data-role="position-save"
              @click="savePosition(item.symbol)"
            >
              {{ savingSymbol === item.symbol ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </SectionCard>
    </section>

    <!-- Tab 2: 组合持仓视图 (Portfolio) -->
    <section v-else-if="activeTab === 'portfolio'" class="grid gap-4">
      <p v-if="portfolioError" class="rounded-[16px] border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ portfolioError }}
      </p>

      <div v-if="portfolioLoading && !portfolioSummary" class="py-6 text-center text-text-faint">正在加载组合数据…</div>

      <template v-else-if="portfolioSummary && hasHoldings">
        <!-- 4大维度汇总卡片 -->
        <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-role="portfolio-summary">
          <article class="surface grid gap-1 rounded-[18px] p-4">
            <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总市值</span>
            <strong class="num text-2xl text-text">{{ formatNumber(portfolioSummary.total_market_value) }}</strong>
            <span class="num text-[11px] text-text-faint">{{ portfolioSummary.priced_position_count }}/{{ portfolioSummary.position_count }} 只有实时行情</span>
          </article>
          <article class="surface grid gap-1 rounded-[18px] p-4">
            <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总未实现盈亏</span>
            <strong class="num text-2xl" :class="pnlToneClass(portfolioSummary.total_unrealized_pnl)">
              {{ formatSignedMoney(portfolioSummary.total_unrealized_pnl) }}
            </strong>
            <span class="num text-[11px]" :class="pnlToneClass(portfolioSummary.total_unrealized_pnl_percent)">
              {{ formatPercent(portfolioSummary.total_unrealized_pnl_percent) }}
            </span>
          </article>
          <article class="surface grid gap-1 rounded-[18px] p-4">
            <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总成本</span>
            <strong class="num text-2xl text-text">{{ formatNumber(portfolioSummary.total_cost_basis) }}</strong>
          </article>
          <article class="surface grid gap-1 rounded-[18px] p-4">
            <span class="text-[11px] uppercase tracking-[0.18em] text-muted">持仓数量</span>
            <strong class="num text-2xl text-text">{{ portfolioSummary.position_count }}</strong>
          </article>
        </section>

        <!-- 持仓明细表 -->
        <SectionCard title="持仓明细与盈亏核算" subtitle="市值 / 成本 / 未实现盈亏 / 仓位权重" eyebrow="Positions">
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] border-collapse text-sm" data-role="portfolio-positions">
              <thead>
                <tr class="border-b border-border text-left text-[11px] uppercase tracking-[0.14em] text-muted">
                  <th class="py-2 pr-3 font-semibold">标的</th>
                  <th class="py-2 px-3 text-right font-semibold">持仓量</th>
                  <th class="py-2 px-3 text-right font-semibold">成本价</th>
                  <th class="py-2 px-3 text-right font-semibold">现价</th>
                  <th class="py-2 px-3 text-right font-semibold">市值</th>
                  <th class="py-2 px-3 text-right font-semibold">未实现盈亏</th>
                  <th class="py-2 pl-3 text-right font-semibold">权重</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="position in portfolioSummary.positions"
                  :key="position.symbol"
                  class="border-b border-border/60"
                  data-role="portfolio-position-row"
                >
                  <td class="py-3 pr-3">
                    <RouterLink
                      :to="{ name: 'watchlist-detail', params: { symbol: position.symbol } }"
                      class="grid gap-0.5"
                    >
                      <span class="font-mono text-[13px] text-text">{{ position.symbol }}</span>
                      <span class="text-[11px] text-muted">{{ position.display_name }}</span>
                    </RouterLink>
                  </td>
                  <td class="py-3 px-3 text-right font-mono tabular-nums text-text-soft">{{ formatNumber(position.position_size) }}</td>
                  <td class="py-3 px-3 text-right font-mono tabular-nums text-text-soft">{{ formatNumber(position.average_cost) }}</td>
                  <td class="py-3 px-3 text-right font-mono tabular-nums">
                    <span v-if="position.current_price !== null" class="text-text-soft">
                      {{ formatNumber(position.current_price) }}
                    </span>
                    <span v-else class="text-[11px] uppercase tracking-[0.12em] text-text-faint">
                      {{ position.price_status }}
                    </span>
                  </td>
                  <td class="py-3 px-3 text-right font-mono tabular-nums text-text-soft">{{ formatNumber(position.market_value) }}</td>
                  <td class="py-3 px-3 text-right font-mono tabular-nums" :class="pnlToneClass(position.unrealized_pnl)">
                    <div class="grid gap-0.5">
                      <span>{{ formatSignedMoney(position.unrealized_pnl) }}</span>
                      <span class="text-[11px]">{{ formatPercent(position.unrealized_pnl_percent) }}</span>
                    </div>
                  </td>
                  <td class="py-3 pl-3 text-right font-mono tabular-nums text-text-soft">{{ weightLabel(position.weight) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </SectionCard>
      </template>

      <SectionCard v-else-if="portfolioSummary" title="尚无持仓数据" subtitle="为任意自选股填写持仓量与成本后，这里会自动生成持仓组合分析">
        <p class="text-text-faint">
          请在下方的持仓设置中，为关注标的输入「持仓量」与「成本价」，系统将立刻开始跟踪您的组合盈亏与加权新闻。
        </p>
      </SectionCard>
    </section>

    <!-- Tab 3: 按仓位加权的新闻视图 (Weighted News) -->
    <section v-else-if="activeTab === 'news'">
      <SectionCard
        title="最该看的持仓重磅新闻"
        subtitle="按“情绪分 × 仓位市值权重”聚合排序，影响你最多钱的消息排在最前"
        eyebrow="Weighted News"
      >
        <p v-if="!portfolioSummary?.weighted_news || portfolioSummary.weighted_news.length === 0" class="py-4 text-text-faint">
          近期没有命中持仓标的带情绪评分的新闻。为自选股设置持仓量后，这里将自动呈现最影响您资产变化的消息。
        </p>
        <ol v-else class="grid gap-2" data-role="portfolio-weighted-news">
          <li
            v-for="(entry, index) in portfolioSummary.weighted_news"
            :key="entry.news_item.id"
            class="grid gap-2 rounded-[16px] border border-border bg-white/[0.02] p-3.5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center"
            data-role="weighted-news-item"
          >
            <span class="num font-mono text-[13px] text-accent">#{{ index + 1 }}</span>
            <div class="grid gap-1">
              <RouterLink
                :to="{ name: 'news-detail', params: { id: entry.news_item.id } }"
                class="text-[14px] leading-snug text-text hover:text-accent"
              >
                {{ entry.news_item.title }}
              </RouterLink>
              <div class="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                <span class="rounded-full border border-border px-2 py-0.5 uppercase tracking-[0.12em]">
                  {{ sentimentText(entry.news_item.sentiment_label) }}
                </span>
                <span
                  v-for="sym in entry.symbols"
                  :key="sym"
                  class="rounded-full border border-accent/30 bg-accent/[0.06] px-2 py-0.5 font-mono text-accent"
                >
                  {{ sym }}
                </span>
                <span class="text-text-faint">{{ entry.news_item.source_name }}</span>
              </div>
            </div>
            <div class="grid justify-items-end gap-0.5 text-right">
              <span class="text-[11px] uppercase tracking-[0.12em] text-muted">影响分</span>
              <strong class="num font-mono text-sm" :class="pnlToneClass(entry.signed_impact)">
                {{ entry.impact_score.toFixed(3) }}
              </strong>
            </div>
          </li>
        </ol>
      </SectionCard>
    </section>

    <!-- 添加自选股票弹窗 Modal -->
    <WatchlistAddModal
      :open="isAddModalOpen"
      :query="addModalQuery"
      :matches="addModalMatches"
      :selected-candidate="addModalSelectedCandidate"
      :advanced-open="addModalAdvancedOpen"
      :alert-threshold="addModalAlertThreshold"
      :create-loading="watchlistStore.createLoading"
      :create-error="watchlistStore.createError"
      :is-searching="isSearching"
      @close="closeAddModal"
      @update-query="addModalQuery = $event"
      @select-candidate="handleSelectAddCandidate"
      @toggle-advanced="addModalAdvancedOpen = !addModalAdvancedOpen"
      @update-alert-threshold="addModalAlertThreshold = $event"
      @submit="handleAddCandidate"
    />
  </div>
</template>

