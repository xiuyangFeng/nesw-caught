<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import WatchlistTable from '../components/watchlist/WatchlistTable.vue';
import { useWatchlistStore } from '../stores/watchlistStore';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const router = useRouter();
const watchlistStore = useWatchlistStore();
const form = reactive({
  symbol: '',
  market: 'hk' as 'hk' | 'us',
  display_name: '',
  alert_threshold: '',
});

const watchlistRows = computed(() => watchlistStore.quotes);
const abnormalMovers = computed(() => watchlistStore.quotes.filter((item) => item.is_abnormal));

const relatedNews = computed(() => {
  const symbol = watchlistStore.selectedSymbol;
  return symbol ? watchlistStore.relatedNews[symbol] ?? [] : [];
});

async function selectSymbol(symbol: string) {
  await watchlistStore.loadRelatedNews(symbol);
  await router.push(`/watchlist/${encodeURIComponent(symbol)}`);
}

async function submitWatchlist() {
  const symbol = form.symbol.trim().toUpperCase();
  const displayName = form.display_name.trim();
  if (!symbol || !displayName) {
    watchlistStore.createError = '请填写股票代码和显示名称';
    return;
  }

  try {
    await watchlistStore.createWatchlist({
      symbol,
      market: form.market,
      display_name: displayName,
      alert_threshold: form.alert_threshold ? Number(form.alert_threshold) : null,
      alert_mode: 'fixed',
    });
    form.symbol = '';
    form.display_name = '';
    form.alert_threshold = '';
  } catch {
    // Error state is handled by the store for inline display.
  }
}

onMounted(async () => {
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
      <SectionCard title="添加自选股" subtitle="写入后端 SQLite，并立即回到自选股列表联动展示">
        <form class="watchlist-form" @submit.prevent="submitWatchlist">
          <label>
            <span>股票代码</span>
            <input v-model.trim="form.symbol" placeholder="例如 AAPL 或 0700.HK" />
          </label>
          <label>
            <span>显示名称</span>
            <input v-model.trim="form.display_name" placeholder="例如 Apple / Tencent" />
          </label>
          <label>
            <span>市场</span>
            <select v-model="form.market">
              <option value="hk">港股</option>
              <option value="us">美股</option>
            </select>
          </label>
          <label>
            <span>阈值（可选）</span>
            <input v-model.trim="form.alert_threshold" type="number" min="0" step="0.1" placeholder="例如 3" />
          </label>
          <button class="submit-button" type="submit" :disabled="watchlistStore.createLoading">
            {{ watchlistStore.createLoading ? '提交中...' : '添加到自选股' }}
          </button>
          <p v-if="watchlistStore.createError" class="error-text">{{ watchlistStore.createError }}</p>
        </form>
      </SectionCard>

      <SectionCard title="自选股总览" subtitle="行情来自 /api/market/watchlist，点击任一股票进入详情页">
        <LoadingBlock :loading="watchlistStore.loading" :empty="watchlistRows.length === 0">
          <WatchlistTable
            :rows="watchlistRows"
            :selected-symbol="watchlistStore.selectedSymbol"
            @select="selectSymbol"
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
  grid-template-columns: 0.8fr 1.1fr 0.9fr;
  gap: 16px;
}

.watchlist-form {
  display: grid;
  gap: 12px;
}

.watchlist-form label {
  display: grid;
  gap: 6px;
  color: var(--text-faint);
  font-size: 14px;
}

.watchlist-form input,
.watchlist-form select {
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
