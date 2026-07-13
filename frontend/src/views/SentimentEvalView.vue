<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type {
  SentimentEvalLabel,
  SentimentEvalResponse,
  SentimentModelRun,
} from '../types/api';

const LABELS: SentimentEvalLabel[] = ['positive', 'negative', 'neutral'];
const LABEL_TEXT: Record<SentimentEvalLabel, string> = {
  positive: '利好 Positive',
  negative: '利空 Negative',
  neutral: '中性 Neutral',
};

const data = ref<SentimentEvalResponse | null>(null);
const loading = ref(false);
const errorMessage = ref<string | null>(null);

const available = computed(() => data.value?.available === true);
const primary = computed<SentimentModelRun | null>(() => data.value?.primary ?? null);
const comparison = computed(() => data.value?.comparison ?? null);

const heroMetrics = computed(() => {
  const metrics = primary.value?.metrics;
  const cmp = comparison.value;
  return [
    { label: 'Accuracy', value: metrics ? fmtPct(metrics.accuracy) : '--', note: '整体准确率', tone: 'default' as const },
    { label: 'Macro F1', value: metrics ? fmtPct(metrics.macro_f1) : '--', note: '三类平均 F1', tone: 'default' as const },
    { label: 'Samples', value: metrics ? String(metrics.sample_count) : '--', note: '金标样本数', tone: 'default' as const },
    {
      label: 'A/B Winner',
      value: cmp ? winnerText(cmp.winner) : '--',
      note: cmp ? `Δ macro-F1 ${fmtDelta(cmp.macro_f1_delta)}` : '两套配置对比',
      tone: cmp?.winner === 'model_b' ? ('positive' as const) : cmp?.winner === 'model_a' ? ('negative' as const) : ('default' as const),
    },
  ];
});

const confusionRows = computed(() => {
  const matrix = primary.value?.metrics.confusion_matrix;
  if (!matrix) {
    return [];
  }
  return LABELS.map((actual) => ({
    actual,
    cells: LABELS.map((predicted) => ({
      predicted,
      count: matrix[actual]?.[predicted] ?? 0,
      diagonal: actual === predicted,
    })),
  }));
});

function fmtPct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtNum(value: number) {
  return value.toFixed(4);
}

function fmtDelta(value: number) {
  const fixed = value.toFixed(4);
  return value > 0 ? `+${fixed}` : fixed;
}

function deltaToneClass(value: number) {
  if (value > 0) {
    return 'text-positive';
  }
  if (value < 0) {
    return 'text-negative';
  }
  return 'text-muted';
}

function winnerText(winner: 'model_a' | 'model_b' | 'tie') {
  if (winner === 'model_a') {
    return 'Model A';
  }
  if (winner === 'model_b') {
    return 'Model B';
  }
  return '持平 Tie';
}

async function loadEval() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const res = await apiClient.getSentimentEval();
    data.value = res.data;
  } catch (err: any) {
    errorMessage.value = err?.message ?? '加载情绪评测失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadEval();
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Model Quality</p>
        <h1 class="page-title">Sentiment Eval</h1>
        <p class="page-subtitle">
          情绪 / 利好利空分类评测闭环：对内置金标集即时评一遍，给出 per-label P/R/F1、混淆矩阵与两套模型配置的 A/B 对比。
        </p>
      </div>
      <button
        type="button"
        class="inline-flex h-9 items-center gap-2 self-start rounded-full border border-border bg-white/[0.04] px-4 text-[12px] font-semibold text-text transition duration-150 ease-out hover:border-system/25 hover:bg-white/[0.06]"
        :disabled="loading"
        @click="loadEval"
      >
        {{ loading ? '评测中…' : '重新评测' }}
      </button>
    </header>

    <p
      v-if="errorMessage"
      class="rounded-[14px] border border-negative/40 bg-negative/10 px-4 py-3 text-[13px] text-negative"
      data-role="sentiment-eval-error"
    >
      {{ errorMessage }}
    </p>

    <p
      v-else-if="data && !available"
      class="rounded-[14px] border border-border-strong bg-white/[0.02] px-4 py-3 text-[13px] text-muted"
      data-role="sentiment-eval-unavailable"
    >
      {{ data.note ?? '金标数据集不可用。' }}
      <span class="block text-[11px] text-text-faint">dataset: {{ data.dataset_path }}</span>
    </p>

    <template v-if="available">
      <!-- 概览指标 -->
      <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-role="sentiment-eval-hero">
        <article
          v-for="metric in heroMetrics"
          :key="metric.label"
          class="surface rounded-[16px] border border-border/80 bg-panel-soft/60 px-4 py-4"
        >
          <p class="text-[10px] uppercase tracking-[0.16em] text-system">{{ metric.label }}</p>
          <strong
            class="mt-1 block text-[26px] leading-none"
            :class="metric.tone === 'positive' ? 'text-positive' : metric.tone === 'negative' ? 'text-negative' : 'text-text'"
          >
            {{ metric.value }}
          </strong>
          <span class="mt-1 block text-[11px] text-muted">{{ metric.note }}</span>
        </article>
      </section>

      <div class="grid gap-4 xl:grid-cols-2">
        <!-- Per-label P/R/F1 -->
        <SectionCard
          eyebrow="Per Label"
          title="逐标签 P / R / F1"
          :subtitle="`模型：${primary?.model_name ?? '--'}`"
          data-role="sentiment-eval-per-label"
        >
          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-[13px]">
              <thead>
                <tr class="text-left text-[11px] uppercase tracking-[0.12em] text-muted">
                  <th class="border-b border-border px-2 py-2">Label</th>
                  <th class="border-b border-border px-2 py-2 text-right">Precision</th>
                  <th class="border-b border-border px-2 py-2 text-right">Recall</th>
                  <th class="border-b border-border px-2 py-2 text-right">F1</th>
                  <th class="border-b border-border px-2 py-2 text-right">Support</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in primary?.metrics.per_label ?? []" :key="row.label">
                  <td class="border-b border-border/60 px-2 py-2">
                    <span class="pill" :class="row.label">{{ LABEL_TEXT[row.label] }}</span>
                  </td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono">{{ fmtNum(row.precision) }}</td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono">{{ fmtNum(row.recall) }}</td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono text-text">{{ fmtNum(row.f1) }}</td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono text-muted">{{ row.support }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </SectionCard>

        <!-- 混淆矩阵 -->
        <SectionCard
          eyebrow="Confusion Matrix"
          title="混淆矩阵"
          subtitle="行=人工标注 · 列=模型预测 · 对角线为命中"
          data-role="sentiment-eval-confusion"
        >
          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-center text-[13px]">
              <thead>
                <tr class="text-[11px] uppercase tracking-[0.1em] text-muted">
                  <th class="border-b border-border px-2 py-2 text-left">Actual \\ Pred</th>
                  <th v-for="label in LABELS" :key="label" class="border-b border-border px-2 py-2">
                    {{ label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in confusionRows" :key="row.actual">
                  <td class="border-b border-border/60 px-2 py-2 text-left text-muted">{{ row.actual }}</td>
                  <td
                    v-for="cell in row.cells"
                    :key="cell.predicted"
                    class="border-b border-border/60 px-2 py-2 font-mono"
                    :class="cell.diagonal
                      ? 'bg-positive/10 font-bold text-positive'
                      : cell.count > 0
                        ? 'text-negative'
                        : 'text-text-faint'"
                  >
                    {{ cell.count }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </SectionCard>
      </div>

      <!-- A/B 对比 -->
      <SectionCard
        v-if="comparison"
        eyebrow="A/B Test"
        title="模型 A/B 对比"
        :subtitle="comparison.reason"
        data-role="sentiment-eval-ab"
      >
        <div class="grid gap-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <article
              v-for="(run, key) in { model_a: comparison.model_a, model_b: comparison.model_b }"
              :key="key"
              class="rounded-[14px] border px-4 py-3"
              :class="comparison.winner === key
                ? 'border-positive/45 bg-positive/[0.06]'
                : 'border-border bg-white/[0.02]'"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-[11px] uppercase tracking-[0.14em] text-system">
                  {{ key === 'model_a' ? 'Model A' : 'Model B' }}
                </span>
                <span
                  v-if="comparison.winner === key"
                  class="rounded-full border border-positive/40 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-positive"
                >
                  Winner
                </span>
              </div>
              <strong class="mt-1 block text-[15px] text-text">{{ run.model_name }}</strong>
              <div class="mt-2 flex gap-4 text-[12px] text-muted">
                <span>Acc <b class="font-mono text-text">{{ fmtNum(run.metrics.accuracy) }}</b></span>
                <span>Macro-F1 <b class="font-mono text-text">{{ fmtNum(run.metrics.macro_f1) }}</b></span>
              </div>
            </article>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-[13px]">
              <thead>
                <tr class="text-left text-[11px] uppercase tracking-[0.12em] text-muted">
                  <th class="border-b border-border px-2 py-2">Label</th>
                  <th class="border-b border-border px-2 py-2 text-right">F1 · Model A</th>
                  <th class="border-b border-border px-2 py-2 text-right">F1 · Model B</th>
                  <th class="border-b border-border px-2 py-2 text-right">Δ F1</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in comparison.label_deltas" :key="row.label">
                  <td class="border-b border-border/60 px-2 py-2">
                    <span class="pill" :class="row.label">{{ LABEL_TEXT[row.label] }}</span>
                  </td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono text-muted">{{ fmtNum(row.f1_before) }}</td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono text-text">{{ fmtNum(row.f1_after) }}</td>
                  <td class="border-b border-border/60 px-2 py-2 text-right font-mono" :class="deltaToneClass(row.f1_delta)">
                    {{ fmtDelta(row.f1_delta) }}
                  </td>
                </tr>
                <tr>
                  <td class="px-2 py-2 text-[12px] uppercase tracking-[0.1em] text-system">Overall</td>
                  <td class="px-2 py-2 text-right font-mono text-muted">{{ fmtNum(comparison.model_a.metrics.accuracy) }}</td>
                  <td class="px-2 py-2 text-right font-mono text-text">{{ fmtNum(comparison.model_b.metrics.accuracy) }}</td>
                  <td class="px-2 py-2 text-right font-mono" :class="deltaToneClass(comparison.accuracy_delta)">
                    {{ fmtDelta(comparison.accuracy_delta) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>
    </template>

    <LoadingBlock
      v-if="!data && !errorMessage"
      :loading="loading"
      :empty="!loading"
      empty-text="尚无评测结果"
      :skeletonCount="2"
    >
      <span />
    </LoadingBlock>
  </div>
</template>
