<script setup lang="ts">
import { computed, ref } from 'vue';

import type { NewsEventMarker, NewsItem, StockKlineResponse, WatchlistDashboardPeriod, WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime } from '../../utils/time';
import KlineChart from './KlineChart.vue';
import ResearchBriefPanel from './ResearchBriefPanel.vue';
import RelatedNewsSidebar from './RelatedNewsSidebar.vue';
import { useWatchlistStore } from '../../stores/watchlistStore';
import { parseMarkdown } from '../../utils/markdown';
import { useToastStore } from '../../stores/toastStore';

const watchlistStore = useWatchlistStore();
const toastStore = useToastStore();

const props = defineProps<{
  quote: WatchlistQuoteSummary | null;
  klineData: StockKlineResponse | null;
  detailNews: NewsItem[];
  researchBrief: import('../../types/api').WatchlistResearchBrief | null;
  currentPeriod: WatchlistDashboardPeriod;
  klineLoading: boolean;
  klineError: string | null;
}>();

const emit = defineEmits<{
  switchPeriod: [period: WatchlistDashboardPeriod];
}>();

const highlightedEventTime = ref<string | null>(null);

const headline = computed(() => props.quote?.display_name ?? props.klineData?.symbol ?? '市场概览');
const symbolLabel = computed(() => props.quote?.symbol ?? props.klineData?.symbol ?? '--');
const lastPrice = computed(() => {
  if (props.quote?.price === null || props.quote?.price === undefined) {
    return '--';
  }
  return props.quote.price.toFixed(2);
});
const changeAmount = computed(() => {
  const value = props.quote?.change_amount;
  if (value === null || value === undefined) {
    return '--';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
});
const updatedAt = computed(() => {
  if (!props.quote?.fetched_at || !props.quote?.market) {
    return '--';
  }
  return formatMarketTime(props.quote.fetched_at, props.quote.market);
});

const candles = computed(() => props.klineData?.candles ?? []);

function clampRatio(value: number | null): number | null {
  if (value === null || Number.isNaN(value)) {
    return null;
  }
  return Math.max(0, Math.min(1, value));
}

function formatRatio(value: number | null): string {
  if (value === null) {
    return '--';
  }
  return `${Math.round(value * 100)}%`;
}

const amplitude = computed(() => {
  if (!props.quote?.previous_close || props.quote.day_high == null || props.quote.day_low == null) {
    return null;
  }
  return ((props.quote.day_high - props.quote.day_low) / props.quote.previous_close) * 100;
});

const sessionPosition = computed(() => {
  const price = props.quote?.price ?? candles.value.at(-1)?.close ?? null;
  const low = props.quote?.day_low ?? null;
  const high = props.quote?.day_high ?? null;
  if (price === null || low === null || high === null || high <= low) {
    return null;
  }
  return clampRatio((price - low) / (high - low));
});

const sixMonthPosition = computed(() => {
  if (!candles.value.length) {
    return null;
  }
  const latest = candles.value.at(-1)?.close ?? null;
  const low = Math.min(...candles.value.map((item) => item.low));
  const high = Math.max(...candles.value.map((item) => item.high));
  if (latest === null || high <= low) {
    return null;
  }
  return clampRatio((latest - low) / (high - low));
});

const averageVolume20 = computed(() => {
  const volumes = candles.value.slice(-20).map((item) => item.volume).filter((item): item is number => item !== null);
  if (!volumes.length) {
    return null;
  }
  return volumes.reduce((sum, value) => sum + value, 0) / volumes.length;
});

const quoteMetrics = computed(() => [
  ['开盘', formatNumber(props.quote?.open_price)],
  ['昨收', formatNumber(props.quote?.previous_close)],
  ['最高', formatNumber(props.quote?.day_high)],
  ['最低', formatNumber(props.quote?.day_low)],
  ['成交量', formatNumber(props.quote?.volume, 0)],
  ['振幅', formatPercent(amplitude.value)],
  ['日内位置', formatRatio(sessionPosition.value)],
  ['20日均量', formatNumber(averageVolume20.value, 0)],
  ['区间位置', formatRatio(sixMonthPosition.value)],
]);

function focusNewsEvent(event: NewsEventMarker) {
  highlightedEventTime.value = event.time;
}

function focusNewsItem(item: NewsItem) {
  highlightedEventTime.value = (item.published_at ?? item.fetched_at).slice(0, 10);
}

const currentSymbol = computed(() => props.quote?.symbol ?? props.klineData?.symbol ?? '');
const aiInsight = computed(() => currentSymbol.value ? (watchlistStore.aiInsights[currentSymbol.value] || null) : null);

async function generateAiInsight() {
  if (!currentSymbol.value) return;
  await watchlistStore.loadAiInsight(currentSymbol.value);
}

async function copyInsight() {
  if (!aiInsight.value?.text) return;
  try {
    await navigator.clipboard.writeText(aiInsight.value.text);
    toastStore.showSuccess('📋 AI 投研报告已成功复制到剪贴板，请随时转发分享！');
  } catch (err) {
    console.error('Failed to copy text', err);
    toastStore.showError('复制失败，请手动选择复制');
  }
}
</script>

<template>
  <section class="grid gap-4" data-role="stock-detail-panel">
    <header
      class="grid gap-2 rounded-lg border border-border bg-panel px-3 py-3"
      data-role="trading-desk-summary"
    >
      <div class="grid gap-3 xl:grid-cols-[minmax(220px,0.78fr)_minmax(0,1.22fr)] xl:items-center">
        <div class="grid gap-1.5" data-role="trading-desk-price-strip">
          <div class="grid gap-0.5">
            <p class="text-[11px] uppercase tracking-[0.24em] text-accent">行情看盘</p>
            <div class="flex flex-wrap items-end gap-x-2 gap-y-1">
              <h2 class="text-[24px] font-semibold leading-none text-text">{{ headline }}</h2>
              <span class="num text-[11px] uppercase tracking-[0.22em] text-text-faint">{{ symbolLabel }}</span>
            </div>
          </div>
          <div class="flex flex-wrap items-end gap-x-2.5 gap-y-1">
            <strong class="num text-[34px] font-semibold leading-none text-text">{{ lastPrice }}</strong>
            <div class="grid gap-0.5">
              <span class="num text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ changeAmount }}
              </span>
              <span class="num text-sm font-semibold" :class="(quote?.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ formatPercent(quote?.change_percent) }}
              </span>
            </div>
          </div>
        </div>
        <div
          class="grid gap-1.5 rounded-md border border-border bg-panel-strong px-3 py-2.5"
          data-role="terminal-quote-matrix"
        >
          <div class="grid grid-cols-2 gap-x-3 gap-y-1.5 md:grid-cols-3 xl:grid-cols-3">
            <article v-for="[label, value] in quoteMetrics" :key="label" class="grid gap-0.5">
              <span class="text-[9px] uppercase tracking-[0.18em] text-text-faint">{{ label }}</span>
              <strong class="num text-sm text-text">{{ value }}</strong>
            </article>
          </div>
        </div>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2 text-[13px] text-text-soft">
        <p>
          {{ klineLoading ? '正在加载最新K线图...' : klineError ? klineError : '上方可快速切换周期，主图与右侧面板分别负责趋势观察和技术读数。' }}
        </p>
        <span class="text-[11px] uppercase tracking-[0.16em] text-text-faint">更新时间 {{ updatedAt }}</span>
      </div>
    </header>

    <section data-role="trading-desk-main">
      <KlineChart
        :kline-data="klineData"
        :current-period="currentPeriod"
        :highlighted-event-time="highlightedEventTime"
        @focus-news="focusNewsEvent"
        @switch-period="emit('switchPeriod', $event)"
      />
    </section>

    <section v-if="researchBrief" data-role="watchlist-detail-research">
      <ResearchBriefPanel :research-brief="researchBrief" />
    </section>

    <!-- AI 投研洞察 (AI Insight Workspace) -->
    <section v-if="currentSymbol" class="grid gap-2" data-role="watchlist-detail-ai-insight">
      <div class="surface rounded-lg border border-border bg-panel px-4 py-4">
        <div class="mb-3.5 flex items-center justify-between gap-3 border-b border-border/40 pb-2">
          <div>
            <p class="text-[10px] uppercase tracking-[0.16em] text-ai font-semibold">✦ AI Intelligence</p>
            <h3 class="text-[15px] font-semibold text-text mt-0.5">AI 投研洞察 (AI Insight)</h3>
          </div>
          <div v-if="aiInsight?.text" class="flex items-center gap-2">
            <!-- 一键复制 -->
            <button
              class="rounded-lg bg-ai/10 hover:bg-ai/20 px-2.5 py-1 text-[11px] text-ai font-semibold transition-colors flex items-center gap-1 active:scale-95"
              type="button"
              @click="copyInsight"
            >
              📋 复制报告
            </button>
            <button
              class="rounded-lg bg-white/[0.05] hover:bg-white/[0.1] px-2.5 py-1 text-[11px] text-text-faint hover:text-text transition-colors"
              type="button"
              :disabled="aiInsight.loading"
              @click="generateAiInsight"
            >
              {{ aiInsight.loading ? '正在研判…' : '🔄 重新生成' }}
            </button>
          </div>
        </div>

        <div class="relative overflow-hidden rounded-xl bg-black/15 p-4 border border-border/40">
          <!-- 未生成且未在加载中 -->
          <div v-if="!aiInsight || (!aiInsight.loading && !aiInsight.text && !aiInsight.error)" class="flex flex-col items-center justify-center py-6 text-center">
            <p class="text-xs text-text-faint mb-3.5 max-w-md">
              尚未生成本自选股的最新 AI 投研研判简报。点击下方按钮即可一键调取大模型进行新闻脱水分析。
            </p>
            <button
              class="flex items-center gap-2 rounded-full bg-grad-ai px-5 py-2.5 text-xs font-semibold text-white shadow-glow-ai transition hover:brightness-110 active:scale-95"
              type="button"
              @click="generateAiInsight"
            >
              ✨ 一键生成 AI 洞察
            </button>
          </div>

          <!-- 加载中 -->
          <div v-else-if="aiInsight.loading" class="flex flex-col items-center justify-center py-8">
            <div class="relative h-9 w-9">
              <div class="absolute inset-0 rounded-full border-2 border-ai/20" />
              <div class="absolute inset-0 rounded-full border-2 border-ai border-t-transparent animate-spin" />
            </div>
            <p class="text-xs text-ai font-semibold mt-4 animate-pulse">
              正在汇聚近期新闻并生成 AI 研判报告…
            </p>
          </div>

          <!-- 报错 -->
          <div v-else-if="aiInsight.error" class="flex flex-col items-center justify-center py-6 text-center">
            <p class="text-xs text-danger mb-3.5">
              {{ aiInsight.error }}
            </p>
            <button
              class="rounded-full bg-white/[0.08] hover:bg-white/[0.15] px-4 py-2 text-xs font-semibold text-text transition"
              type="button"
              @click="generateAiInsight"
            >
              重试一次
            </button>
          </div>

          <!-- 正常展示（Markdown 渲染） -->
          <div v-else-if="aiInsight.text" class="grid gap-2">
            <!-- Failover Alert Banner -->
            <div
              v-if="aiInsight.failover"
              class="p-2.5 rounded-xl border border-warning/30 bg-warning/10 text-[11px] text-warning flex items-center gap-2 select-text"
            >
              <span class="animate-pulse">⚡</span>
              <span>
                <strong>故障接管</strong>：由于默认模型 <code>{{ aiInsight.failover.from_model }}</code> 访问异常，已无缝切换至备用模型 <code>{{ aiInsight.failover.to_model }}</code> 进行研报生成。
              </span>
            </div>
            <!-- 采用 renderMarkdown 渲染 -->
            <div
              class="markdown-content text-[12px] leading-[1.65] text-text-muted space-y-2 select-text"
              v-html="parseMarkdown(aiInsight.text)"
            />
          </div>
        </div>
      </div>
    </section>

    <section class="grid gap-4" data-role="watchlist-detail-news">
      <RelatedNewsSidebar :items="detailNews" :highlighted-event-time="highlightedEventTime" @focus-news="focusNewsItem" />
    </section>
  </section>
</template>
