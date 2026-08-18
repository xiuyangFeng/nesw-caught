<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { PortfolioSummary, QuantPaperAccount, QuantPaperOrder } from '../types/api';
import { formatNumber, formatPercent, sentimentText } from '../utils/format';
import { formatMarketTime } from '../utils/time';

const summary = ref<PortfolioSummary | null>(null);
const paper = ref<QuantPaperAccount | null>(null);
const lastOrder = ref<QuantPaperOrder | null>(null);
const paperSymbol = ref('600519.SH');
const paperQuantity = ref(100);
const paperConfirmed = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);

const hasHoldings = computed(() => (summary.value?.positions.length ?? 0) > 0);

async function loadPortfolio() {
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.getPortfolio();
    summary.value = response.data;
  } catch {
    error.value = '组合数据加载失败，请检查后端服务';
  } finally {
    loading.value = false;
  }
}

async function loadPaper() {
  try {
    const response = await apiClient.getQuantPaperAccount();
    paper.value = response.data;
  } catch {
    paper.value = null;
  }
}

async function submitPaperOrder() {
  try {
    const response = await apiClient.placeQuantPaperOrder({
      symbol: paperSymbol.value,
      side: 'buy',
      quantity: paperQuantity.value,
      confirmed: paperConfirmed.value,
    });
    lastOrder.value = response.data;
    await loadPaper();
  } catch (err) {
    lastOrder.value = {
      id: null,
      status: 'rejected',
      filled: false,
      reason: err instanceof Error ? err.message : '下单失败',
      price: null,
    };
  }
}

// 盈亏红绿：>=0 绿(success)，<0 红(danger)，缺失灰(muted)。
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

const generatedAtLabel = computed(() => {
  if (!summary.value?.generated_at) {
    return null;
  }
  return formatMarketTime(summary.value.generated_at, 'us');
});

onMounted(() => {
  void loadPortfolio();
  void loadPaper();
});
</script>

<template>
  <div class="grid gap-4" data-role="portfolio-view">
    <header class="flex flex-col gap-3 rounded-[24px] border border-border bg-panel p-5 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-[11px] uppercase tracking-[0.24em] text-accent">Portfolio</span>
          <RouterLink to="/watchlist?tab=portfolio" class="rounded-full bg-accent/10 px-2.5 py-0.5 text-[10px] text-accent border border-accent/30 hover:bg-accent/20">
            一体化工作台 ↗
          </RouterLink>
        </div>
        <h1 class="page-title mb-1.5 mt-1">持仓 · 组合</h1>
        <p class="page-subtitle">按持仓量与成本核算实时盈亏，并把影响你最多钱的新闻排到最前。</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <RouterLink
          to="/watchlist"
          class="rounded-full border border-border px-4 py-1.5 text-[11px] uppercase tracking-[0.16em] text-text hover:border-accent/40"
        >
          📈 前往自选行情
        </RouterLink>
        <button
          class="w-fit rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:bg-accent/20 disabled:cursor-progress disabled:opacity-60"
          :disabled="loading"
          data-role="portfolio-refresh"
          @click="loadPortfolio"
        >
          {{ loading ? '刷新中...' : '刷新组合' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="rounded-[16px] border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
      {{ error }}
    </p>

    <SectionCard
      v-if="paper"
      eyebrow="Paper"
      title="模拟盘"
      subtitle="确认后才撮合；停牌/涨跌停拒单与回测一致。探索性策略不得晋级实盘。"
    >
      <p class="text-sm text-text" data-role="portfolio-paper-cash">
        现金 {{ formatNumber(paper.cash) }} / 初始 {{ formatNumber(paper.initial_cash) }}
      </p>
      <p class="mt-1 text-xs text-muted">{{ paper.note }}</p>
      <div class="mt-3 flex flex-wrap items-end gap-2">
        <label class="grid gap-1 text-xs text-muted">
          标的
          <input v-model="paperSymbol" class="rounded-md border border-border bg-panel px-2 py-1 text-sm text-text" data-role="portfolio-paper-symbol" />
        </label>
        <label class="grid gap-1 text-xs text-muted">
          数量
          <input v-model.number="paperQuantity" type="number" class="rounded-md border border-border bg-panel px-2 py-1 text-sm text-text" data-role="portfolio-paper-qty" />
        </label>
        <label class="flex items-center gap-2 text-xs text-muted">
          <input v-model="paperConfirmed" type="checkbox" data-role="portfolio-paper-confirm" />
          已确认次日开盘撮合
        </label>
        <button type="button" class="rounded-md border border-accent px-3 py-1.5 text-sm text-accent" data-role="portfolio-paper-submit" @click="submitPaperOrder">
          提交模拟买单
        </button>
      </div>
      <p v-if="lastOrder" class="mt-2 text-sm text-muted" data-role="portfolio-paper-result">
        {{ lastOrder.status }} · {{ lastOrder.filled ? '已成交' : lastOrder.reason }}
      </p>
    </SectionCard>

    <div v-if="loading && !summary" class="text-text-faint">正在加载组合数据…</div>

    <template v-else-if="summary && hasHoldings">
      <!-- 汇总卡片 -->
      <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-role="portfolio-summary">
        <article class="surface grid gap-1 rounded-[18px] p-4">
          <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总市值</span>
          <strong class="num text-2xl text-text">{{ formatNumber(summary.total_market_value) }}</strong>
          <span class="num text-[11px] text-text-faint">{{ summary.priced_position_count }}/{{ summary.position_count }} 只有实时行情</span>
        </article>
        <article class="surface grid gap-1 rounded-[18px] p-4">
          <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总未实现盈亏</span>
          <strong class="num text-2xl" :class="pnlToneClass(summary.total_unrealized_pnl)">
            {{ formatSignedMoney(summary.total_unrealized_pnl) }}
          </strong>
          <span class="num text-[11px]" :class="pnlToneClass(summary.total_unrealized_pnl_percent)">
            {{ formatPercent(summary.total_unrealized_pnl_percent) }}
          </span>
        </article>
        <article class="surface grid gap-1 rounded-[18px] p-4">
          <span class="text-[11px] uppercase tracking-[0.18em] text-muted">总成本</span>
          <strong class="num text-2xl text-text">{{ formatNumber(summary.total_cost_basis) }}</strong>
        </article>
        <article class="surface grid gap-1 rounded-[18px] p-4">
          <span class="text-[11px] uppercase tracking-[0.18em] text-muted">持仓数量</span>
          <strong class="num text-2xl text-text">{{ summary.position_count }}</strong>
          <span v-if="generatedAtLabel" class="num text-[11px] text-text-faint">{{ generatedAtLabel }} 更新</span>
        </article>
      </section>

      <!-- 各持仓明细 -->
      <SectionCard title="持仓明细" subtitle="市值 / 成本 / 未实现盈亏 / 仓位权重" eyebrow="Positions">
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
                v-for="position in summary.positions"
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

      <!-- 按仓位加权的新闻 -->
      <SectionCard
        title="最该看的新闻"
        subtitle="按“情绪分 × 仓位市值权重”聚合排序，影响你最多钱的消息排在最前"
        eyebrow="Weighted News"
      >
        <p v-if="summary.weighted_news.length === 0" class="text-text-faint">
          近期没有命中持仓的带情绪评分新闻。
        </p>
        <ol v-else class="grid gap-2" data-role="portfolio-weighted-news">
          <li
            v-for="(entry, index) in summary.weighted_news"
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
    </template>

    <SectionCard v-else-if="summary" title="尚无持仓" subtitle="为自选股填写持仓量与成本后，这里会展示组合盈亏">
      <p class="text-text-faint">
        前往
        <RouterLink to="/watchlist" class="text-accent">自选股</RouterLink>
        页，为任意标的填写「持仓量 / 成本」即可开始跟踪组合盈亏与加权新闻。
      </p>
    </SectionCard>
  </div>
</template>
