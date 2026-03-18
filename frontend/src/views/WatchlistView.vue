<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import WatchlistTable from '../components/watchlist/WatchlistTable.vue';
import { useWatchlistStore } from '../stores/watchlistStore';
import type { WatchlistCandidate } from '../types/api';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const router = useRouter();
const watchlistStore = useWatchlistStore();
const selectedCandidate = ref<WatchlistCandidate | null>(null);
const form = reactive({
  query: '',
  alert_threshold: '',
});

const watchlistRows = computed(() => watchlistStore.quotes);
const abnormalMovers = computed(() => watchlistStore.quotes.filter((item) => item.is_abnormal));
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
  <div class="page">
    <header class="page-header">
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

    <section class="watchlist-layout">
      <SectionCard title="管理自选股" subtitle="输入名称或代码片段即可联想候选，添加与删除都在同一块面板完成">
        <form class="watchlist-toolbar" @submit.prevent="submitWatchlist">
          <label class="search-field">
            <span>搜索股票</span>
            <input v-model.trim="form.query" placeholder="输入股票代码、中文名或英文名" />
            <div v-if="filteredCandidates.length" class="candidate-list">
              <button
                v-for="candidate in filteredCandidates"
                :key="candidate.symbol"
                class="candidate-option"
                type="button"
                :disabled="isCandidateAdded(candidate.symbol)"
                @click="selectCandidate(candidate)"
              >
                <span class="candidate-main">
                  <strong>{{ candidate.display_name }}</strong>
                  <small>{{ candidate.symbol }} · {{ candidate.market.toUpperCase() }}</small>
                </span>
                <span class="candidate-state">{{ isCandidateAdded(candidate.symbol) ? '已添加' : '选择' }}</span>
              </button>
            </div>
          </label>

          <label>
            <span>阈值（可选）</span>
            <input v-model.trim="form.alert_threshold" type="number" min="0" step="0.1" placeholder="例如 3" />
          </label>

          <button class="submit-button" type="submit" :disabled="watchlistStore.createLoading || !selectedCandidate">
            {{ watchlistStore.createLoading ? '提交中...' : '添加到自选股' }}
          </button>

          <p v-if="selectedCandidate" class="selection-hint">
            已选择 {{ selectedCandidate.display_name }} · {{ selectedCandidate.symbol }}
          </p>
          <p v-if="watchlistStore.createError" class="error-text">{{ watchlistStore.createError }}</p>
          <p v-if="watchlistStore.deleteError" class="error-text">{{ watchlistStore.deleteError }}</p>
          <p v-if="watchlistStore.candidateError" class="error-text">{{ watchlistStore.candidateError }}</p>
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

      <SectionCard title="关联新闻" subtitle="这里保留为快速预览，完整行情指标请进入单股详情页查看">
        <LoadingBlock
          :loading="watchlistStore.relatedLoading"
          :empty="!watchlistStore.selectedSymbol || relatedNews.length === 0"
          empty-text="当前股票暂无关联新闻"
        >
          <div class="related-list">
            <article v-for="item in relatedNews" :key="item.id" class="related-card">
              <div class="related-head">
                <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                <span>{{ item.source_name }}</span>
              </div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.summary }}</p>
              <span class="related-time">
                {{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}
              </span>
            </article>
          </div>
        </LoadingBlock>
      </SectionCard>
    </section>
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

.watchlist-layout {
  display: grid;
  grid-template-columns: 1.5fr 0.9fr;
  gap: 16px;
}

.watchlist-toolbar {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.watchlist-toolbar label {
  display: grid;
  gap: 6px;
  color: var(--text-faint);
  font-size: 14px;
}

.watchlist-toolbar input {
  border-radius: 12px;
  border: 1px solid var(--border);
  padding: 10px 12px;
  font: inherit;
  background: var(--field-bg);
  color: var(--text);
}

.submit-button {
  border: none;
  border-radius: 999px;
  padding: 12px 16px;
  font: inherit;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.submit-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(58, 169, 245, 0.24);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: progress;
  box-shadow: none;
}

.error-text {
  margin: 0;
  color: var(--negative);
}

.selection-hint {
  margin: 0;
  color: var(--text-soft);
}

.search-field {
  position: relative;
}

.candidate-list {
  display: grid;
  gap: 8px;
  margin-top: 6px;
  padding: 10px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(8, 15, 28, 0.94);
}

.candidate-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.72);
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.candidate-option:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.candidate-main {
  display: grid;
  gap: 4px;
}

.candidate-main small,
.candidate-state {
  color: var(--text-faint);
}

.related-list {
  display: grid;
  gap: 12px;
}

.related-card {
  border-radius: 18px;
  padding: 16px;
  background: var(--panel-stronger);
  border: 1px solid var(--border);
  box-shadow: 0 14px 30px rgba(2, 6, 12, 0.24);
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.related-card:hover {
  border-color: rgba(125, 211, 252, 0.22);
  transform: translateY(-1px);
}

.related-head {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--text-faint);
  font-size: 12px;
}

.related-card strong {
  color: var(--text);
}

.related-card p,
.related-time {
  color: var(--text-soft);
}
</style>
