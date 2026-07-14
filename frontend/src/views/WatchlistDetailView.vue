<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import StockDetailPanel from '../components/watchlist/StockDetailPanel.vue';
import { HttpError } from '../api/http';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useWatchlistStore } from '../stores/watchlistStore';
import { apiClient } from '../api/client';
import { useToastStore } from '../stores/toastStore';
import type { StockResearchRating, StockResearchReport } from '../types/api';

const route = useRoute();
const router = useRouter();
const watchlistStore = useWatchlistStore();
const toastStore = useToastStore();

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase());
const detailQuote = computed(() => watchlistStore.quoteDetail);

// --- 个股 AI 综合研判（本地语料 RAG，结构化研报）本地视图态 ---
const research = ref<StockResearchReport | null>(null);
const researchLoading = ref(false);
const researchError = ref<string | null>(null);
const lookbackDays = ref(7);
const LOOKBACK_OPTIONS = [7, 14, 30];

// 评级枚举 -> 中文标签 + 语义配色（红涨绿跌：看多=正向红，看空=负向绿，中性=琥珀告警）。
const RATING_META: Record<StockResearchRating, { label: string; classes: string }> = {
  strong_bullish: { label: '强烈看多', classes: 'border-positive/40 bg-positive/10 text-positive' },
  bullish: { label: '看多', classes: 'border-positive/30 bg-positive/[0.07] text-positive' },
  neutral: { label: '中性', classes: 'border-warning/30 bg-warning/[0.07] text-warning' },
  bearish: { label: '看空', classes: 'border-negative/30 bg-negative/[0.07] text-negative' },
  strong_bearish: { label: '强烈看空', classes: 'border-negative/40 bg-negative/10 text-negative' },
  unknown: { label: '数据不足', classes: 'border-border bg-panel-strong text-text-faint' },
};

const ratingMeta = computed(() => (research.value ? RATING_META[research.value.overall_rating] : null));

// 后端对带默认值的数组字段在 OpenAPI 中标记为可选，这里统一兜底为空数组。
const bullCase = computed(() => research.value?.bull_case ?? []);
const bearCase = computed(() => research.value?.bear_case ?? []);
const keyEvents = computed(() => research.value?.key_events ?? []);
const references = computed(() => research.value?.references ?? []);

function impactDotClass(impact: string): string {
  if (impact === 'positive') return 'bg-positive';
  if (impact === 'negative') return 'bg-negative';
  return 'bg-muted';
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '--';
  return iso.slice(0, 10);
}

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

async function generateResearch() {
  const target = detailQuote.value?.symbol ?? symbol.value;
  if (!target) return;
  researchLoading.value = true;
  researchError.value = null;
  try {
    const { data } = await apiClient.getStockResearch(target, lookbackDays.value);
    research.value = data;
  } catch (error) {
    const message = error instanceof HttpError ? error.message : '生成 AI 综合研判失败，请稍后再试';
    researchError.value = message;
    toastStore.showError(message);
  } finally {
    researchLoading.value = false;
  }
}

function selectLookback(days: number) {
  if (lookbackDays.value === days) return;
  lookbackDays.value = days;
  if (research.value || researchError.value) {
    void generateResearch();
  }
}

async function copyResearch() {
  const report = research.value;
  if (!report) return;
  const bull = report.bull_case ?? [];
  const bear = report.bear_case ?? [];
  const events = report.key_events ?? [];
  const lines: string[] = [
    `【${report.display_name ?? report.symbol}（${report.symbol}）AI 综合研判】`,
    `评级：${RATING_META[report.overall_rating].label}（近 ${report.lookback_days} 天，命中新闻 ${report.news_count} 条）`,
    '',
    report.summary,
  ];
  if (bull.length) {
    lines.push('', '催化剂 / 利好：', ...bull.map((item) => `· ${item}`));
  }
  if (bear.length) {
    lines.push('', '风险 / 利空：', ...bear.map((item) => `· ${item}`));
  }
  if (events.length) {
    lines.push('', '关键时间线：', ...events.map((e) => `· ${formatDate(e.date)} ${e.title}`));
  }
  try {
    await navigator.clipboard.writeText(lines.join('\n'));
    toastStore.showSuccess('📋 AI 综合研判已复制到剪贴板');
  } catch (err) {
    console.error('Failed to copy research', err);
    toastStore.showError('复制失败，请手动选择复制');
  }
}

onMounted(async () => {
  await loadPageData(symbol.value);
});

watch(symbol, async (nextSymbol, previousSymbol) => {
  if (nextSymbol && nextSymbol !== previousSymbol) {
    // 切换标的时清空上一只股票的研判结果，避免串号。
    research.value = null;
    researchError.value = null;
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

    <!-- 个股 AI 综合研判（结构化研报） -->
    <section v-if="symbol" class="grid gap-2" data-role="stock-ai-research">
      <div
        class="rounded-lg border border-border bg-panel px-4 py-4"
      >
        <div class="mb-3.5 flex flex-wrap items-center justify-between gap-3 border-b border-border/40 pb-2.5">
          <div>
            <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-ai">✦ Local RAG Synthesis</p>
            <h3 class="mt-0.5 text-[15px] font-semibold text-text">🧠 AI 综合研判</h3>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <div class="flex items-center gap-1 rounded-full bg-white/[0.04] p-0.5">
              <button
                v-for="option in LOOKBACK_OPTIONS"
                :key="option"
                class="rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors"
                :class="lookbackDays === option ? 'bg-accent/15 text-accent' : 'text-text-faint hover:text-text'"
                type="button"
                @click="selectLookback(option)"
              >
                近{{ option }}天
              </button>
            </div>
            <button
              v-if="research"
              class="flex items-center gap-1 rounded-lg bg-white/[0.05] px-2.5 py-1 text-[11px] text-purple-300 transition-colors hover:bg-white/[0.1]"
              type="button"
              @click="copyResearch"
            >
              📋 复制
            </button>
            <button
              v-if="research || researchError"
              class="rounded-lg bg-white/[0.05] px-2.5 py-1 text-[11px] text-text-faint transition-colors hover:bg-white/[0.1] hover:text-text"
              type="button"
              :disabled="researchLoading"
              @click="generateResearch"
            >
              {{ researchLoading ? '研判中…' : '🔄 重新生成' }}
            </button>
          </div>
        </div>

        <div class="relative overflow-hidden rounded-xl border border-border/40 bg-black/15 p-4">
          <!-- 未生成 -->
          <div
            v-if="!research && !researchLoading && !researchError"
            class="flex flex-col items-center justify-center py-6 text-center"
          >
            <p class="mb-3.5 max-w-md text-xs text-text-faint">
              汇总本股票近 {{ lookbackDays }} 天的命中新闻、正文与价格走势，基于本地语料检索一键生成结构化研报（评级 / 催化剂 / 风险 / 关键时间线）。
            </p>
            <button
              class="flex items-center gap-2 rounded-full bg-grad-ai px-5 py-2.5 text-xs font-semibold text-white shadow-glow-ai transition hover:brightness-110 active:scale-95"
              type="button"
              @click="generateResearch"
            >
              🧠 生成 AI 综合研判
            </button>
          </div>

          <!-- 加载中 -->
          <div v-else-if="researchLoading" class="flex flex-col items-center justify-center py-8">
            <div class="relative h-9 w-9">
              <div class="absolute inset-0 rounded-full border-2 border-accent/20" />
              <div class="absolute inset-0 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            </div>
            <p class="mt-4 animate-pulse text-xs font-semibold text-accent">正在检索本地语料并综合研判…</p>
          </div>

          <!-- 报错 -->
          <div v-else-if="researchError" class="flex flex-col items-center justify-center py-6 text-center">
            <p class="mb-3.5 text-xs text-danger">{{ researchError }}</p>
            <button
              class="rounded-full bg-white/[0.08] px-4 py-2 text-xs font-semibold text-text transition hover:bg-white/[0.15]"
              type="button"
              @click="generateResearch"
            >
              重试一次
            </button>
          </div>

          <!-- 研报展示 -->
          <div v-else-if="research" class="grid gap-4 select-text">
            <!-- 顶栏：评级 + 元信息 -->
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-3">
                <span
                  v-if="ratingMeta"
                  class="rounded-lg border px-3 py-1.5 text-sm font-bold tracking-wide"
                  :class="ratingMeta.classes"
                >
                  {{ ratingMeta.label }}
                </span>
                <div class="text-[11px] text-text-faint">
                  <span>近 {{ research.lookback_days }} 天 · 命中 {{ research.news_count }} 条新闻</span>
                </div>
              </div>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                :class="research.mode === 'llm' ? 'bg-purple-500/10 text-purple-300' : 'bg-white/[0.05] text-text-faint'"
              >
                {{ research.mode === 'llm' ? `AI · ${research.model_name ?? 'LLM'}` : '规则汇总' }}
              </span>
            </div>

            <!-- 降级 / 故障接管提示 -->
            <div
              v-if="research.mode === 'rule' && research.llm_error"
              class="rounded-xl border border-warning/30 bg-warning/10 p-2.5 text-[11px] text-warning"
            >
              大模型暂不可用，已降级为基于新闻情绪的规则要点汇总。
            </div>
            <div
              v-if="research.failover"
              class="flex items-center gap-2 rounded-xl border border-warning/30 bg-warning/10 p-2.5 text-[11px] text-warning"
            >
              <span class="animate-pulse">⚡</span>
              <span>
                <strong>故障接管</strong>：默认模型 <code>{{ research.failover.from_model }}</code> 异常，已切换至
                <code>{{ research.failover.to_model }}</code> 生成研报。
              </span>
            </div>

            <!-- 摘要 -->
            <p class="text-[13px] leading-[1.7] text-text-muted">{{ research.summary }}</p>
            <p v-if="research.rating_rationale" class="text-[12px] leading-[1.6] text-text-faint">
              评级依据：{{ research.rating_rationale }}
            </p>

            <!-- 价格走势 -->
            <div class="grid grid-cols-2 gap-2 rounded-xl border border-border/40 bg-white/[0.02] px-3 py-2.5 md:grid-cols-4">
              <div class="grid gap-0.5">
                <span class="text-[9px] uppercase tracking-[0.16em] text-text-faint">最新价</span>
                <strong class="text-sm text-text">{{ research.price_context.price ?? '--' }}</strong>
              </div>
              <div class="grid gap-0.5">
                <span class="text-[9px] uppercase tracking-[0.16em] text-text-faint">最新涨跌</span>
                <strong
                  class="text-sm"
                  :class="(research.price_context.change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'"
                >
                  {{ formatPercent(research.price_context.change_percent) }}
                </strong>
              </div>
              <div class="grid gap-0.5">
                <span class="text-[9px] uppercase tracking-[0.16em] text-text-faint">窗口累计</span>
                <strong
                  class="text-sm"
                  :class="(research.price_context.window_change_percent ?? 0) >= 0 ? 'text-positive' : 'text-negative'"
                >
                  {{ formatPercent(research.price_context.window_change_percent) }}
                </strong>
              </div>
              <div class="grid gap-0.5">
                <span class="text-[9px] uppercase tracking-[0.16em] text-text-faint">区间高/低</span>
                <strong class="text-sm text-text">
                  {{ research.price_context.window_high ?? '--' }} / {{ research.price_context.window_low ?? '--' }}
                </strong>
              </div>
            </div>

            <!-- 催化剂 / 风险 -->
            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded-xl border border-positive/20 bg-positive/[0.05] p-3">
                <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-positive">📈 催化剂 / 利好</p>
                <ul v-if="bullCase.length" class="grid gap-1.5">
                  <li v-for="(item, idx) in bullCase" :key="idx" class="flex gap-2 text-[12px] leading-relaxed text-text-muted">
                    <span class="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-positive" />
                    <span>{{ item }}</span>
                  </li>
                </ul>
                <p v-else class="text-[12px] text-text-faint">暂无明显利好信号。</p>
              </div>
              <div class="rounded-xl border border-negative/20 bg-negative/[0.05] p-3">
                <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-negative">📉 风险 / 利空</p>
                <ul v-if="bearCase.length" class="grid gap-1.5">
                  <li v-for="(item, idx) in bearCase" :key="idx" class="flex gap-2 text-[12px] leading-relaxed text-text-muted">
                    <span class="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-negative" />
                    <span>{{ item }}</span>
                  </li>
                </ul>
                <p v-else class="text-[12px] text-text-faint">暂无明显风险信号。</p>
              </div>
            </div>

            <!-- 关键时间线 -->
            <div v-if="keyEvents.length" class="grid gap-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-text-faint">🗓 关键时间线</p>
              <ol class="grid gap-2 border-l border-border/40 pl-3">
                <li v-for="(event, idx) in keyEvents" :key="idx" class="relative grid gap-0.5">
                  <span
                    class="absolute -left-[15px] top-1.5 h-2 w-2 rounded-full ring-2 ring-[#0b0f18]"
                    :class="impactDotClass(event.impact)"
                  />
                  <div class="flex items-baseline gap-2">
                    <span class="text-[11px] tabular-nums text-text-faint">{{ formatDate(event.date) }}</span>
                    <span class="text-[12px] font-semibold text-text">{{ event.title }}</span>
                  </div>
                  <p v-if="event.description" class="text-[11px] leading-relaxed text-text-muted">{{ event.description }}</p>
                </li>
              </ol>
            </div>

            <!-- 引用新闻 -->
            <div v-if="references.length" class="grid gap-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-text-faint">
                📎 语料来源（{{ references.length }}）
              </p>
              <ul class="grid gap-1">
                <li v-for="ref in references" :key="ref.news_id" class="flex items-baseline gap-2 text-[11px]">
                  <span class="tabular-nums text-text-faint">{{ formatDate(ref.published_at) }}</span>
                  <a
                    v-if="ref.canonical_url"
                    class="truncate text-system hover:underline hover:brightness-110"
                    :href="ref.canonical_url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {{ ref.title }}
                  </a>
                  <span v-else class="truncate text-text-muted">{{ ref.title }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
