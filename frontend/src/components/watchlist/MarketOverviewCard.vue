<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

import type { MarketNewsSignalItem, MarketOverviewMarket } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';

const props = defineProps<{
  data: MarketOverviewMarket;
}>();

const router = useRouter();

// ^VIX 只参与美股量化情绪计算,不单独成行展示(设计文档十三.1 定案);
// 后端即使下发也在前端过滤,双保险。
const visibleIndices = computed(() => props.data.indices.filter((index) => index.symbol !== '^VIX'));

// 涨跌配色沿用 StockCard.vue 的全局约定(--positive 红涨 / --negative 绿跌)。
function changeToneClass(value: number | null | undefined) {
  if ((value ?? 0) > 0) {
    return 'text-positive';
  }
  if ((value ?? 0) < 0) {
    return 'text-negative';
  }
  return 'text-text-soft';
}

// 量化情绪 chip 五色映射(设计文档十节):panic 红 / fear 橙 / neutral 灰 /
// greed 浅绿 / greed_extreme 深绿;unknown 与其它缺数据场景统一灰色"数据不足"。
// 绿色使用主题里的 --negative 变量(本主题绿跌色),保持配色体系一致。
const SENTIMENT_CHIP_STYLES: Record<string, { text: string; class: string }> = {
  panic: { text: '恐慌', class: 'border-danger/40 bg-danger/10 text-danger' },
  fear: { text: '偏慌', class: 'border-warning/40 bg-warning/10 text-warning' },
  neutral: { text: '中性', class: 'border-border bg-white/5 text-text-faint' },
  greed: {
    text: '贪婪',
    class: 'border-[color-mix(in_srgb,var(--negative)_40%,transparent)] bg-[var(--negative-soft)] text-[var(--negative)]',
  },
  greed_extreme: {
    text: '极度贪婪',
    class: 'border-transparent bg-[var(--negative)] text-white',
  },
  unknown: { text: '数据不足', class: 'border-border bg-white/5 text-text-faint' },
};

const sentimentChip = computed(() => {
  const label = props.data.quant_sentiment?.label ?? 'unknown';
  return SENTIMENT_CHIP_STYLES[label] ?? SENTIMENT_CHIP_STYLES.unknown;
});

const boards = computed(() => props.data.boards);
const showBoards = computed(() => boards.value.source !== 'none');
const boardTitle = computed(() => (boards.value.source === 'eastmoney' ? '行业板块(东财)' : '板块代理 ETF'));

const newsSentiment = computed(() => props.data.news_sentiment);
const newsUsable = computed(
  () => newsSentiment.value !== null && newsSentiment.value.status === 'ok' && newsSentiment.value.score !== null,
);

function openSignal(signal: MarketNewsSignalItem) {
  router.push({ name: 'news-detail', params: { id: signal.news_id } });
}
</script>

<template>
  <article
    class="grid content-start gap-3 rounded-xl border border-border/80 bg-panel px-3.5 py-3"
    :data-role="`market-overview-card-${data.market}`"
  >
    <!-- 头部:市场名 + 开闭市徽标 + 量化情绪 chip -->
    <header class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2 min-w-0">
        <strong class="truncate text-sm font-bold text-text">{{ data.display_name }}</strong>
        <span
          class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
          :class="data.is_open ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border bg-white/5 text-text-faint'"
          data-role="market-open-badge"
        >
          {{ data.is_open ? '开盘中' : '已闭市' }}
        </span>
      </div>
      <span
        class="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
        :class="sentimentChip.class"
        data-role="quant-sentiment-chip"
        :title="data.quant_sentiment?.score !== null && data.quant_sentiment?.score !== undefined
          ? `量化情绪分 ${data.quant_sentiment.score.toFixed(2)}`
          : '量化情绪数据不足'"
      >
        {{ sentimentChip.text }}
      </span>
    </header>

    <!-- 指数行列表 -->
    <div class="grid gap-1">
      <div
        v-for="index in visibleIndices"
        :key="index.symbol"
        class="flex items-center justify-between gap-2 text-[12px]"
        :data-role="`overview-index-${index.symbol}`"
      >
        <span class="truncate text-text-soft">{{ index.display_name }}</span>
        <span class="flex shrink-0 items-baseline gap-2 font-mono tabular-nums">
          <span class="text-text">{{ formatNumber(index.price) }}</span>
          <span class="font-semibold" :class="changeToneClass(index.change_percent)" data-role="overview-index-change">
            {{ formatPercent(index.change_percent) }}
          </span>
        </span>
      </div>
      <p v-if="visibleIndices.length === 0" class="text-[11px] text-text-faint">未配置指数</p>
    </div>

    <!-- 板块区:cn 东财榜 / us,eu 代理 ETF / kr,jp(source=none) 不渲染 -->
    <section v-if="showBoards" class="grid gap-1 border-t border-border/60 pt-2" data-role="board-section">
      <div class="flex items-center justify-between">
        <span class="text-[10px] uppercase tracking-[0.14em] text-text-faint">{{ boardTitle }}</span>
        <span v-if="boards.stale" class="rounded-full border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[9px] text-warning">
          数据滞后
        </span>
      </div>
      <p v-if="boards.status !== 'ok'" class="text-[11px] text-text-faint">板块数据暂不可用</p>
      <template v-else>
        <div
          v-for="item in boards.items"
          :key="item.code"
          class="flex items-center justify-between gap-2 text-[12px]"
          :data-role="`board-item-${item.code}`"
        >
          <span class="truncate text-text-soft">{{ item.name }}</span>
          <span class="shrink-0 font-mono font-semibold tabular-nums" :class="changeToneClass(item.change_percent)">
            {{ formatPercent(item.change_percent) }}
          </span>
        </div>
        <p v-if="boards.items.length === 0" class="text-[11px] text-text-faint">暂无板块数据</p>
      </template>
    </section>

    <!-- 新闻情绪:分数 + 重要信号列表(点击跳新闻详情);缺数据优雅降级 -->
    <section class="grid gap-1 border-t border-border/60 pt-2" data-role="news-sentiment-section">
      <div class="flex items-center justify-between">
        <span class="text-[10px] uppercase tracking-[0.14em] text-text-faint">新闻情绪</span>
        <span
          v-if="newsUsable"
          class="font-mono text-[12px] font-semibold tabular-nums"
          :class="changeToneClass(newsSentiment?.score)"
        >
          {{ newsSentiment?.score?.toFixed(2) }}
        </span>
      </div>
      <template v-if="newsUsable">
        <button
          v-for="signal in newsSentiment?.top_signals ?? []"
          :key="signal.news_id"
          type="button"
          class="grid gap-0.5 rounded-lg border border-transparent px-1.5 py-1 text-left transition hover:border-accent/40 hover:bg-accent/5"
          :data-role="`news-signal-${signal.news_id}`"
          @click="openSignal(signal)"
        >
          <span class="truncate text-[12px] leading-snug text-text">{{ signal.title }}</span>
          <span class="flex items-center gap-1.5 text-[10px] text-text-faint">
            <span v-if="signal.source_name">{{ signal.source_name }}</span>
            <span>置信度 {{ Math.round((signal.signal_confidence ?? 0) * 100) }}%</span>
          </span>
        </button>
      </template>
      <p v-else-if="newsSentiment?.status === 'insufficient_data'" class="text-[11px] text-text-faint">
        样本不足,暂无情绪分
      </p>
      <p v-else class="text-[11px] text-text-faint">暂无数据</p>
    </section>
  </article>
</template>
