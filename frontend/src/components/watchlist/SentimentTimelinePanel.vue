<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { apiClient } from '../../api/client';
import { HttpError } from '../../api/http';
import type { DivergenceStatusValue, SentimentTimelinePoint, SentimentTimelineResponse } from '../../types/api';

// 个股情绪时间线面板：近 N 天新闻情绪走势（手写 SVG 柱状图，风格对齐
// components/dashboard/SentimentTrendChart.vue 的暗色霓虹惯例）+ hover 显示当日
// top_news 标题 + 顶部情绪-价格背离徽章。组件内自取数（apiClient.getSentimentTimeline），
// 不进 watchlistStore，避免与协作者改动 watchlistStore.ts 冲突。
const props = withDefaults(
  defineProps<{
    symbol: string;
    days?: number;
  }>(),
  {
    days: 30,
  },
);

const data = ref<SentimentTimelineResponse | null>(null);
const loading = ref(false);
const errorMessage = ref<string | null>(null);
const hoveredDate = ref<string | null>(null);

const points = computed<SentimentTimelinePoint[]>(() => data.value?.points ?? []);
const divergence = computed(() => data.value?.divergence ?? null);
const effectiveDays = computed(() => data.value?.days ?? props.days);

const DIVERGENCE_META: Record<DivergenceStatusValue, { label: string; classes: string }> = {
  bearish_divergence: {
    label: '情绪-价格背离：情绪偏多但价格走弱',
    classes: 'border-negative/40 bg-negative/10 text-negative',
  },
  bullish_divergence: {
    label: '情绪-价格背离：情绪偏空但价格走强',
    classes: 'border-positive/40 bg-positive/10 text-positive',
  },
};

const divergenceMeta = computed(() => {
  const status = divergence.value?.status;
  return status ? DIVERGENCE_META[status] : null;
});

async function load() {
  const symbol = props.symbol;
  if (!symbol) {
    return;
  }
  loading.value = true;
  errorMessage.value = null;
  try {
    const { data: response } = await apiClient.getSentimentTimeline(symbol, props.days);
    data.value = response;
  } catch (error) {
    data.value = null;
    errorMessage.value = error instanceof HttpError ? error.message : '情绪时间线加载失败，请稍后再试';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});

watch(
  () => props.symbol,
  (next, previous) => {
    if (next && next !== previous) {
      data.value = null;
      hoveredDate.value = null;
      void load();
    }
  },
);

// -----------------------------------------------------------------------
// SVG 柱状图布局：以 0 为基线，正情绪向上（positive 色）、负情绪向下（negative 色），
// 风格与 views/SignalBacktestView.vue 的分桶柱状图一致。
// -----------------------------------------------------------------------
const chartWidth = 640;
const chartHeight = 140;
const paddingX = 16;
const paddingY = 18;
const zeroLineY = computed(() => paddingY + (chartHeight - paddingY * 2) / 2);

const maxAbsScore = computed(() => {
  const values = points.value.map((point) => Math.abs(point.avg_score));
  const max = values.length ? Math.max(...values) : 0;
  return max > 0 ? max : 1;
});

interface Bar {
  date: string;
  positive: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  centerX: number;
  point: SentimentTimelinePoint;
}

const bars = computed<Bar[]>(() => {
  const items = points.value;
  if (items.length === 0) {
    return [];
  }
  const innerWidth = chartWidth - paddingX * 2;
  const halfHeight = (chartHeight - paddingY * 2) / 2;
  const slot = innerWidth / items.length;
  const barWidth = Math.min(24, slot * 0.6);
  return items.map((point, index) => {
    const ratio = point.avg_score / maxAbsScore.value;
    const barHeight = Math.max(Math.abs(ratio) * halfHeight, 1.5);
    const centerX = paddingX + slot * index + slot / 2;
    const x = centerX - barWidth / 2;
    const y = point.avg_score >= 0 ? zeroLineY.value - barHeight : zeroLineY.value;
    return {
      date: point.date,
      positive: point.avg_score >= 0,
      x,
      y,
      width: barWidth,
      height: barHeight,
      centerX,
      point,
    };
  });
});

const hoveredBar = computed(() => bars.value.find((bar) => bar.date === hoveredDate.value) ?? null);

function formatDateShort(date: string): string {
  return date.slice(5);
}

function formatScore(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
}

function formatPriceChange(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}
</script>

<template>
  <SectionCard
    eyebrow="Sentiment Timeline"
    title="个股情绪时间线"
    :subtitle="`近 ${effectiveDays} 天相关新闻情绪走势，柱状图上方按 |情绪分数| 展示当日 top 新闻`"
    data-role="sentiment-timeline-panel"
  >
    <template #actions>
      <span
        v-if="divergenceMeta"
        class="rounded-full border px-3 py-1 text-[11px] font-semibold"
        :class="divergenceMeta.classes"
        data-role="sentiment-divergence-badge"
      >
        {{ divergenceMeta.label }}
      </span>
    </template>

    <div v-if="loading && !data" class="py-8 text-center text-[13px] text-muted" data-role="sentiment-timeline-loading">
      加载中…
    </div>
    <div v-else-if="errorMessage" class="py-6 text-center text-[13px] text-danger" data-role="sentiment-timeline-error">
      {{ errorMessage }}
    </div>
    <div v-else-if="points.length === 0" class="py-8 text-center text-[13px] text-muted" data-role="sentiment-timeline-empty">
      近 {{ effectiveDays }} 天暂无相关新闻情绪数据
    </div>
    <div v-else class="grid gap-3">
      <svg
        :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
        class="w-full h-auto overflow-visible"
        role="img"
        aria-label="个股情绪时间线柱状图"
        data-role="sentiment-timeline-chart"
      >
        <line
          :x1="paddingX"
          :y1="zeroLineY"
          :x2="chartWidth - paddingX"
          :y2="zeroLineY"
          stroke="var(--border-strong)"
          stroke-width="1"
          stroke-dasharray="4,4"
        />
        <g
          v-for="bar in bars"
          :key="bar.date"
          data-role="sentiment-timeline-bar"
          :data-date="bar.date"
          @mouseenter="hoveredDate = bar.date"
          @mouseleave="hoveredDate = null"
        >
          <rect
            :x="bar.x - 6"
            :y="paddingY"
            :width="bar.width + 12"
            :height="chartHeight - paddingY * 2"
            fill="transparent"
          />
          <rect
            :x="bar.x"
            :y="bar.y"
            :width="bar.width"
            :height="bar.height"
            rx="2"
            :fill="bar.positive ? 'var(--positive)' : 'var(--negative)'"
            :fill-opacity="bar.date === hoveredDate ? 1 : 0.8"
          />
          <text
            :x="bar.centerX"
            :y="chartHeight - 2"
            text-anchor="middle"
            class="fill-muted"
            style="font-size: 9px"
          >
            {{ formatDateShort(bar.date) }}
          </text>
        </g>
      </svg>

      <div
        v-if="hoveredBar"
        class="rounded-lg border border-border/60 bg-panel-soft px-3 py-2 text-[12px]"
        data-role="sentiment-timeline-tooltip"
      >
        <p class="mb-1 text-muted">
          {{ hoveredBar.date }} · 均值 {{ formatScore(hoveredBar.point.avg_score) }} · {{ hoveredBar.point.news_count }} 条新闻
        </p>
        <ul class="grid gap-0.5">
          <li v-for="news in hoveredBar.point.top_news" :key="news.id" class="truncate text-text">
            {{ news.title }}
          </li>
        </ul>
      </div>

      <div
        v-if="divergence && divergence.status"
        class="text-[11px] text-muted"
        data-role="sentiment-divergence-detail"
      >
        窗口 {{ divergence.window_days }} 天 · 情绪均值 {{ formatScore(divergence.sentiment_avg ?? 0) }} ·
        价格变动 {{ formatPriceChange(divergence.price_change_percent) }} · 新闻 {{ divergence.news_count }} 条
      </div>
    </div>
  </SectionCard>
</template>
