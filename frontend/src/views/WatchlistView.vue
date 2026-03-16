<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import WatchlistTable from '../components/watchlist/WatchlistTable.vue';
import { useMarketStore } from '../stores/marketStore';
import { useWatchlistStore } from '../stores/watchlistStore';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

const marketStore = useMarketStore();
const watchlistStore = useWatchlistStore();
const form = reactive({
  symbol: '',
  market: 'hk' as 'hk' | 'us',
  display_name: '',
  alert_threshold: '',
});

const watchlistRows = computed(() =>
  watchlistStore.items.map((item) => ({
    ...item,
    snapshot: marketStore.snapshots.find((snapshot) => snapshot.symbol === item.symbol),
  })),
);

const relatedNews = computed(() => {
  const symbol = watchlistStore.selectedSymbol;
  return symbol ? watchlistStore.relatedNews[symbol] ?? [] : [];
});

async function selectSymbol(symbol: string) {
  await watchlistStore.loadRelatedNews(symbol);
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
  if (!marketStore.snapshots.length) {
    await marketStore.loadSnapshots();
  }
  if (watchlistStore.selectedSymbol) {
    await selectSymbol(watchlistStore.selectedSymbol);
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Watchlist</h1>
        <p class="page-subtitle">自选股、异动状态和关联新闻联动展示，支持盘中快速定位消息源。</p>
      </div>
      <StaleBadge :stale="watchlistStore.stale || marketStore.stale" label="自选股与行情" />
    </header>

    <StatusBanner
      :title="marketStore.abnormalMovers.length ? '检测到自选股异动' : '当前没有明显异动'"
      :tone="marketStore.abnormalMovers.length ? 'warning' : 'default'"
      detail="列表展示价格、涨跌幅、异动原因，右侧保留股票关联新闻入口。"
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

      <SectionCard title="自选股总览" subtitle="价格和异动来自 /api/market/snapshots，列表来自 /api/watchlist">
        <LoadingBlock :loading="watchlistStore.loading || marketStore.loading" :empty="watchlistRows.length === 0">
          <WatchlistTable
            :rows="watchlistRows"
            :selected-symbol="watchlistStore.selectedSymbol"
            @select="selectSymbol"
          />
        </LoadingBlock>
      </SectionCard>

      <SectionCard title="关联新闻" subtitle="从自选股跳转到命中新闻，保留来源、情绪和市场时区">
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
                {{ formatMarketTime(item.published_at, item.market) }} {{ getMarketTimezoneLabel(item.market) }}
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
  color: var(--muted);
  font-size: 14px;
}

.watchlist-form input,
.watchlist-form select {
  border-radius: 12px;
  border: 1px solid var(--border);
  padding: 10px 12px;
  font: inherit;
  background: rgba(255, 255, 255, 0.85);
}

.submit-button {
  border: none;
  border-radius: 999px;
  padding: 12px 16px;
  font: inherit;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #1453a3, #1e7acb);
  cursor: pointer;
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: progress;
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
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border);
}

.related-head {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--muted);
  font-size: 12px;
}

.related-card p,
.related-time {
  color: var(--muted);
}
</style>
