<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { BacktestSummary, Market } from '../types/api';
import { formatMarketTime } from '../utils/time';

// -------------------------------------------------------------------------
// 查询过滤状态：市场 / 回看窗口天数 / 前视时间窗
// -------------------------------------------------------------------------
const selectedMarket = ref<Market | ''>('');
const selectedWindow = ref<number>(30);
const selectedHorizon = ref<string>('1d');

const summary = ref<BacktestSummary | null>(null);
const loading = ref(false);
const errorMessage = ref<string | null>(null);

const markets: Array<{ label: string; value: Market | '' }> = [
  { label: '全部', value: '' },
  { label: 'A股', value: 'cn' },
  { label: '港股', value: 'hk' },
  { label: '美股', value: 'us' },
];

const windows = [7, 30, 90];
const horizons = ['1h', '4h', '1d'];

// importance 分桶的中文标签
const bucketLabelMap: Record<string, string> = {
  high: '高置信',
  medium: '中置信',
  low: '低置信',
  unknown: '未知',
};

async function loadSummary() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const res = await apiClient.getBacktestSummary({
      market: selectedMarket.value || undefined,
      window_days: selectedWindow.value,
      horizon: selectedHorizon.value,
    });
    summary.value = res.data;
  } catch (err: any) {
    errorMessage.value = err?.message || '回测数据加载失败';
    summary.value = null;
  } finally {
    loading.value = false;
  }
}

function selectMarket(value: Market | '') {
  selectedMarket.value = value;
  void loadSummary();
}

function selectWindow(value: number) {
  selectedWindow.value = value;
  void loadSummary();
}

function selectHorizon(value: string) {
  selectedHorizon.value = value;
  void loadSummary();
}

onMounted(() => {
  void loadSummary();
});

// -------------------------------------------------------------------------
// 展示辅助
// -------------------------------------------------------------------------
function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatSignedPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return '—';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

const overviewMetrics = computed(() => {
  const s = summary.value;
  const base = [
    { label: '候选样本', value: s ? String(s.total_signals) : '—', note: '窗口内含方向情绪并可映射股票' },
    { label: '可评估', value: s ? String(s.evaluable_count) : '—', note: '成功取到基准价与前视价' },
    { label: '已跳过', value: s ? String(s.skipped_count) : '—', note: '快照稀疏无法评估' },
    { label: '可评估率', value: s ? formatPercent(s.evaluable_rate) : '—', note: '可评估 / 候选样本' },
  ];
  // 以下为工作块 E（回测方法学修复）additive 新字段，后端未跑新版回测时为
  // null/undefined，此处优雅降级为不渲染对应卡片，不改变旧字段的展示。
  if (s?.distinct_news_count !== null && s?.distinct_news_count !== undefined) {
    base.push({ label: '去重新闻数', value: String(s.distinct_news_count), note: '按新闻去重后的样本来源条数，避免一条新闻多只股票被当独立样本' });
  }
  if (s?.per_news_hit_rate !== null && s?.per_news_hit_rate !== undefined) {
    base.push({ label: '按新闻加权命中率', value: formatPercent(s.per_news_hit_rate), note: '每条新闻先取其提及股票的方向命中均值，再对新闻求均值' });
  }
  if (s?.skipped_stale_count !== null && s?.skipped_stale_count !== undefined) {
    base.push({ label: '陈旧快照跳过', value: String(s.skipped_stale_count), note: 'baseline 快照距新闻发布超过阈值而跳过（计入「已跳过」）' });
  }
  return base;
});

// 工作块 E1：超额收益（相对基准），benchmark_note 说明基准来源（真实指数 / 代理基准）。
const excessReturnDisplay = computed(() => {
  const value = summary.value?.avg_excess_return;
  if (value === null || value === undefined) {
    return null;
  }
  return { value, note: summary.value?.benchmark_note ?? null };
});

// 工作块 E4：按 |sentiment_score| 分桶的回测统计，替代 importance 桶的信息量局限。
const scoreBuckets = computed(() => summary.value?.score_buckets ?? []);

// 工作块 E5：置信度校准（映射表 + 建议阈值），null 表示尚未生成或落盘缺失。
const calibration = computed(() => summary.value?.calibration ?? null);

function formatScoreValue(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return value.toFixed(2);
}

const directionCards = computed(() => {
  const s = summary.value;
  if (!s) {
    return [];
  }
  return [
    {
      key: 'positive',
      title: '利好信号命中率',
      caption: '后续上涨占比',
      tone: 'positive' as const,
      stats: s.positive,
    },
    {
      key: 'negative',
      title: '利空信号命中率',
      caption: '后续下跌占比',
      tone: 'negative' as const,
      stats: s.negative,
    },
  ];
});

const buckets = computed(() => summary.value?.importance_buckets ?? []);

// SVG 柱状图布局：以 0 为基线，正收益向上、负收益向下
const chartWidth = 360;
const chartHeight = 160;
const chartPaddingX = 20;
const chartPaddingY = 20;
const zeroLineY = computed(() => chartPaddingY + (chartHeight - chartPaddingY * 2) / 2);

const maxAbsReturn = computed(() => {
  const values = buckets.value
    .map((b) => b.avg_forward_return)
    .filter((v): v is number => v !== null && v !== undefined)
    .map((v) => Math.abs(v));
  const max = values.length ? Math.max(...values) : 0;
  return max > 0 ? max : 0.01;
});

const bars = computed(() => {
  const items = buckets.value;
  if (items.length === 0) {
    return [];
  }
  const innerWidth = chartWidth - chartPaddingX * 2;
  const halfHeight = (chartHeight - chartPaddingY * 2) / 2;
  const slot = innerWidth / items.length;
  const barWidth = Math.min(48, slot * 0.5);
  return items.map((item, index) => {
    const value = item.avg_forward_return ?? 0;
    const ratio = value / maxAbsReturn.value;
    const barHeight = Math.abs(ratio) * halfHeight;
    const centerX = chartPaddingX + slot * index + slot / 2;
    const x = centerX - barWidth / 2;
    const y = value >= 0 ? zeroLineY.value - barHeight : zeroLineY.value;
    return {
      bucket: item.bucket,
      label: bucketLabelMap[item.bucket] ?? item.bucket,
      sampleCount: item.sample_count,
      value: item.avg_forward_return,
      positive: value >= 0,
      x,
      y,
      width: barWidth,
      height: barHeight,
      centerX,
    };
  });
});

const generatedAtLabel = computed(() => {
  if (!summary.value) {
    return '—';
  }
  return `${formatMarketTime(summary.value.generated_at, 'hk')} HKT`;
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-accent">Analytics · Validation Loop</p>
        <h1 class="page-title">Signal Backtest</h1>
        <p class="page-subtitle">
          信号有效性回测：对历史利好/利空判断，回看发布后前视时间窗内被提及股票的实际价格变动，闭环验证命中率与后续收益。
        </p>
      </div>
      <div class="flex items-center gap-2 self-start text-[11px] uppercase tracking-[0.14em] text-muted">
        <span class="num rounded-full border border-border bg-white/[0.03] px-3 py-1">Generated {{ generatedAtLabel }}</span>
      </div>
    </header>

    <!-- 过滤器 -->
    <section
      class="surface rounded-[14px] border border-border/80 bg-panel-soft/60 px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-3"
      data-role="backtest-filters"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">市场</span>
        <button
          v-for="m in markets"
          :key="m.value || 'all'"
          class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
          :class="selectedMarket === m.value ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
          type="button"
          @click="selectMarket(m.value)"
        >
          {{ m.label }}
        </button>
      </div>

      <div class="flex items-center gap-1.5">
        <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">回看窗口</span>
        <button
          v-for="w in windows"
          :key="w"
          class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
          :class="selectedWindow === w ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
          type="button"
          @click="selectWindow(w)"
        >
          {{ w }}天
        </button>
      </div>

      <div class="flex items-center gap-1.5">
        <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">前视窗</span>
        <button
          v-for="h in horizons"
          :key="h"
          class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
          :class="selectedHorizon === h ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
          type="button"
          @click="selectHorizon(h)"
        >
          {{ h }}
        </button>
      </div>
    </section>

    <!-- 错误提示 -->
    <div
      v-if="errorMessage"
      class="surface rounded-[14px] border border-danger/40 bg-danger/[0.06] px-4 py-3 text-[13px] text-danger"
      data-role="backtest-error"
    >
      {{ errorMessage }}
    </div>

    <!-- 概览指标 -->
    <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-role="backtest-overview">
      <article
        v-for="metric in overviewMetrics"
        :key="metric.label"
        class="surface rounded-[16px] border border-border/80 px-4 py-3.5 grid gap-1.5"
        data-role="backtest-metric"
      >
        <span class="text-[10px] uppercase tracking-[0.16em] text-muted">{{ metric.label }}</span>
        <strong class="num text-[26px] leading-none text-text" :class="{ 'opacity-40': loading }">{{ metric.value }}</strong>
        <small class="text-[11px] leading-4 text-muted">{{ metric.note }}</small>
      </article>
    </section>

    <!-- 平均超额收益（工作块 E1，additive，无数据时不渲染） -->
    <section
      v-if="excessReturnDisplay"
      class="surface rounded-[14px] border border-border/80 bg-panel-soft/60 px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1.5"
      data-role="backtest-excess-return"
    >
      <div>
        <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">平均超额收益</span>
        <strong class="num text-[16px]" :class="excessReturnDisplay.value >= 0 ? 'text-positive' : 'text-negative'">
          {{ formatSignedPercent(excessReturnDisplay.value) }}
        </strong>
        <span class="ml-1 text-[10px] text-muted">= 前视收益 − 基准收益</span>
      </div>
      <span v-if="excessReturnDisplay.note" class="text-[11px] text-muted">{{ excessReturnDisplay.note }}</span>
    </section>

    <!-- 方向命中率 -->
    <section class="grid gap-3 xl:grid-cols-2" data-role="backtest-directions">
      <article
        v-for="card in directionCards"
        :key="card.key"
        class="surface rounded-[18px] border px-5 py-4 grid gap-3"
        :class="card.tone === 'positive' ? 'border-positive/20' : 'border-negative/20'"
        data-role="backtest-direction"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted">{{ card.caption }}</p>
            <h3 class="m-0 mt-1 text-[16px] text-text">{{ card.title }}</h3>
          </div>
          <span class="pill" :class="card.tone">{{ card.key }}</span>
        </div>
        <div class="flex items-end gap-4">
          <div>
            <strong class="num block text-[36px] leading-none" :class="card.tone === 'positive' ? 'text-positive' : 'text-negative'">
              {{ formatPercent(card.stats.hit_rate) }}
            </strong>
            <small class="num text-[11px] text-muted">命中 {{ card.stats.hit_count }} / {{ card.stats.sample_count }} 样本</small>
          </div>
          <div class="ml-auto text-right">
            <span class="block text-[11px] uppercase tracking-[0.14em] text-muted">平均前视收益</span>
            <strong class="num text-[20px] leading-tight" :class="(card.stats.avg_forward_return ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
              {{ formatSignedPercent(card.stats.avg_forward_return) }}
            </strong>
          </div>
        </div>
      </article>
    </section>

    <!-- importance 分桶收益 -->
    <SectionCard
      eyebrow="Importance Buckets"
      title="按信号置信度分桶的平均前视收益"
      subtitle="以 0 为基线，正收益向上、负收益向下；置信度取自信号分类器 signal_confidence"
      data-role="backtest-buckets"
    >
      <div v-if="bars.length === 0" class="py-8 text-center text-[13px] text-muted">
        {{ loading ? '加载中…' : '当前过滤条件下暂无可评估样本' }}
      </div>
      <div v-else class="grid gap-4">
        <svg
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          class="w-full h-auto overflow-visible"
          role="img"
          aria-label="importance 分桶平均前视收益柱状图"
          data-role="backtest-bucket-chart"
        >
          <!-- 零基线 -->
          <line
            :x1="chartPaddingX"
            :y1="zeroLineY"
            :x2="chartWidth - chartPaddingX"
            :y2="zeroLineY"
            stroke="var(--border-strong)"
            stroke-width="1"
            stroke-dasharray="4,4"
          />
          <g v-for="bar in bars" :key="bar.bucket">
            <rect
              :x="bar.x"
              :y="bar.y"
              :width="bar.width"
              :height="bar.height"
              rx="3"
              :fill="bar.positive ? 'var(--positive)' : 'var(--negative)'"
              :fill-opacity="bar.value === null ? 0.15 : 0.85"
            />
            <text
              :x="bar.centerX"
              :y="bar.positive ? bar.y - 6 : bar.y + bar.height + 14"
              text-anchor="middle"
              class="fill-text font-mono"
              style="font-size: 10px"
            >
              {{ formatSignedPercent(bar.value) }}
            </text>
            <text
              :x="bar.centerX"
              :y="chartHeight - 2"
              text-anchor="middle"
              class="fill-muted"
              style="font-size: 10px"
            >
              {{ bar.label }}
            </text>
          </g>
        </svg>

        <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="bar in bars"
            :key="`${bar.bucket}-legend`"
            class="rounded-[12px] border border-border/70 bg-white/[0.02] px-3 py-2"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-[12px] text-text">{{ bar.label }}</span>
              <span class="text-[11px] text-muted">n={{ bar.sampleCount }}</span>
            </div>
            <strong
              class="text-[15px]"
              :class="(bar.value ?? 0) >= 0 ? 'text-positive' : 'text-negative'"
            >
              {{ formatSignedPercent(bar.value) }}
            </strong>
          </div>
        </div>
      </div>
    </SectionCard>

    <!-- 按情绪分数分桶（工作块 E4，additive，替代性地放在 importance 桶旁边） -->
    <SectionCard
      v-if="scoreBuckets.length > 0"
      eyebrow="Score Buckets"
      title="按情绪分数分桶的回测统计"
      subtitle="按 |sentiment_score| 分桶，而非 importance 桶：分数分桶信息量更高，importance 桶见上方"
      data-role="backtest-score-buckets"
    >
      <div class="overflow-x-auto">
        <table class="w-full border-collapse text-[12px]" data-role="backtest-score-buckets-table">
          <thead>
            <tr class="border-b border-border/60 text-left text-[10px] uppercase tracking-wider text-muted">
              <th class="py-1.5 pr-3 font-semibold">分数区间</th>
              <th class="py-1.5 pr-3 font-semibold">样本数</th>
              <th class="py-1.5 pr-3 font-semibold">命中率</th>
              <th class="py-1.5 pr-3 font-semibold">平均前视收益</th>
              <th class="py-1.5 pr-3 font-semibold">平均超额收益</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bucket in scoreBuckets" :key="bucket.range_label" class="border-b border-border/30 last:border-0">
              <td class="py-1.5 pr-3 text-text">{{ bucket.range_label }}</td>
              <td class="num py-1.5 pr-3 text-muted">{{ bucket.sample_count }}</td>
              <td class="num py-1.5 pr-3" :class="(bucket.hit_rate ?? 0) >= 0.5 ? 'text-positive' : 'text-negative'">
                {{ formatPercent(bucket.hit_rate) }}
              </td>
              <td class="num py-1.5 pr-3" :class="(bucket.avg_forward_return ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ formatSignedPercent(bucket.avg_forward_return) }}
              </td>
              <td class="num py-1.5 pr-3" :class="(bucket.avg_excess_return ?? 0) >= 0 ? 'text-positive' : 'text-negative'">
                {{ formatSignedPercent(bucket.avg_excess_return) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <!-- 置信度校准（工作块 E5，additive，后端未生成校准文件时不渲染） -->
    <SectionCard
      v-if="calibration"
      eyebrow="Confidence Calibration"
      title="置信度校准"
      subtitle="按分数桶的经验方向命中率校准 signal_confidence；样本数 < 30 的桶灰显（回退线性公式值）"
      data-role="backtest-calibration"
    >
      <div class="grid gap-4">
        <div class="overflow-x-auto">
          <table class="w-full border-collapse text-[12px]" data-role="backtest-calibration-table">
            <thead>
              <tr class="border-b border-border/60 text-left text-[10px] uppercase tracking-wider text-muted">
                <th class="py-1.5 pr-3 font-semibold">分数区间</th>
                <th class="py-1.5 pr-3 font-semibold">样本数</th>
                <th class="py-1.5 pr-3 font-semibold">经验命中率</th>
                <th class="py-1.5 pr-3 font-semibold">校准置信度</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(entry, index) in calibration.mapping"
                :key="`${entry.score_min}-${entry.score_max}-${index}`"
                class="border-b border-border/30 last:border-0"
                :class="{ 'opacity-40': entry.low_sample }"
                :data-low-sample="entry.low_sample ? 'true' : 'false'"
              >
                <td class="py-1.5 pr-3 text-text">{{ formatScoreValue(entry.score_min) }} ~ {{ formatScoreValue(entry.score_max) }}</td>
                <td class="num py-1.5 pr-3 text-muted">
                  {{ entry.sample_count }}
                  <span v-if="entry.low_sample" class="ml-1 text-[10px] text-warning">样本不足</span>
                </td>
                <td class="num py-1.5 pr-3 text-text">{{ formatPercent(entry.hit_rate) }}</td>
                <td class="num py-1.5 pr-3 text-text">{{ formatPercent(entry.calibrated_confidence) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap gap-4" data-role="backtest-calibration-thresholds">
          <div class="rounded-[12px] border border-border/70 bg-white/[0.02] px-3 py-2">
            <span class="block text-[10px] uppercase tracking-wider text-muted">建议看多阈值</span>
            <strong class="num text-[15px] text-positive">{{ formatScoreValue(calibration.suggested_positive_threshold) }}</strong>
          </div>
          <div class="rounded-[12px] border border-border/70 bg-white/[0.02] px-3 py-2">
            <span class="block text-[10px] uppercase tracking-wider text-muted">建议看空阈值</span>
            <strong class="num text-[15px] text-negative">{{ formatScoreValue(calibration.suggested_negative_threshold) }}</strong>
          </div>
        </div>
      </div>
    </SectionCard>
  </div>
</template>
