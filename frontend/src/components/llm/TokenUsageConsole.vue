<script setup lang="ts">
import { computed } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import TokenTrendChart from './TokenTrendChart.vue';
import type { TokenModelStats, TokenStats } from './types';

const props = defineProps<{
  stats: TokenStats;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

const totalCalls = computed(() => props.stats.models.reduce((sum, model) => sum + (model.call_count || 0), 0));
const sortedModels = computed(() => [...props.stats.models].sort((left, right) => right.total_tokens - left.total_tokens));
const topModel = computed(() => sortedModels.value[0] ?? null);
const promptRatio = computed(() => (
  props.stats.overall.total_tokens > 0
    ? Math.round((props.stats.overall.prompt_tokens / props.stats.overall.total_tokens) * 100)
    : 0
));
const budgetWidth = computed(() => Math.min(100, Math.max(0, (props.stats.budget?.usage_ratio ?? 0) * 100)));
const sortedOperations = computed(() => [...props.stats.operations].sort((left, right) => right.total_tokens - left.total_tokens));

function formatUsd(value: number | null | undefined, digits = 4): string {
  return value != null ? `$${value.toFixed(digits)}` : '—';
}

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}K`;
  return value.toLocaleString();
}

function modelShare(model: TokenModelStats): number {
  if (props.stats.overall.total_tokens <= 0) return 0;
  return Math.round((model.total_tokens / props.stats.overall.total_tokens) * 100);
}
</script>

<template>
  <SectionCard
    eyebrow="USAGE LEDGER"
    title="模型用量账本"
    subtitle="快速查看 Token 流向、成本、调用频率与模型占比"
  >
    <template #actions>
      <button
        class="rounded-full border border-border bg-panel-strong px-3 py-1.5 text-xs text-text-faint transition hover:border-accent hover:text-text disabled:cursor-wait disabled:opacity-60"
        type="button"
        data-role="refresh-token-usage"
        :disabled="loading"
        @click="emit('refresh')"
      >
        {{ loading ? '同步中…' : '刷新账本' }}
      </button>
    </template>

    <div class="grid gap-4">
      <section
        class="grid overflow-hidden rounded-[20px] border border-border/70 bg-black/10 sm:grid-cols-2 xl:grid-cols-[1.35fr_1fr_0.8fr_1.15fr]"
        data-role="usage-metric-strip"
      >
        <article class="relative grid gap-2 border-b border-border/60 p-4 sm:border-r xl:border-b-0">
          <span class="absolute inset-y-0 left-0 w-0.5 bg-accent" />
          <p class="label-mono text-[9px] text-text-faint">TOTAL TOKENS</p>
          <strong class="font-mono text-2xl tabular-nums text-text">{{ stats.overall.total_tokens.toLocaleString() }}</strong>
          <div class="h-1.5 overflow-hidden rounded-full bg-panel-strong">
            <span class="flex h-full">
              <i class="h-full bg-accent" :style="{ width: `${promptRatio}%` }" />
              <i class="h-full bg-ai" :style="{ width: `${100 - promptRatio}%` }" />
            </span>
          </div>
          <p class="flex justify-between font-mono text-[10px] text-text-faint">
            <span>输入 {{ formatCompact(stats.overall.prompt_tokens) }}</span>
            <span>输出 {{ formatCompact(stats.overall.completion_tokens) }}</span>
          </p>
        </article>

        <article class="grid content-center gap-1 border-b border-border/60 p-4 xl:border-b-0 xl:border-r">
          <p class="label-mono text-[9px] text-text-faint">ESTIMATED COST</p>
          <strong class="font-mono text-xl tabular-nums text-success">
            {{ stats.overall.cost_available ? formatUsd(stats.overall.cost_usd) : '—' }}
          </strong>
          <p class="text-[10px] text-text-faint">{{ stats.overall.cost_available ? '按配置单价估算' : '尚未配置单价' }}</p>
        </article>

        <article class="grid content-center gap-1 border-b border-border/60 p-4 sm:border-r xl:border-b-0">
          <p class="label-mono text-[9px] text-text-faint">API CALLS</p>
          <strong class="font-mono text-xl tabular-nums text-ai">{{ totalCalls.toLocaleString() }}</strong>
          <p class="text-[10px] text-text-faint">{{ stats.models.length }} 个活跃模型</p>
        </article>

        <article class="grid min-w-0 content-center gap-1 p-4">
          <p class="label-mono text-[9px] text-text-faint">TOP MODEL</p>
          <strong class="truncate text-sm text-text">{{ topModel?.model_name ?? '暂无模型' }}</strong>
          <p class="font-mono text-[10px] text-warning">
            {{ topModel ? `${modelShare(topModel)}% Token 占比` : '—' }}
          </p>
        </article>
      </section>

      <section
        v-if="stats.budget?.budget_available"
        class="grid gap-2 rounded-[16px] border px-4 py-3"
        :class="stats.budget.over_budget ? 'border-danger/50 bg-danger/10' : 'border-border/70 bg-panel/45'"
        data-testid="llm-budget-banner"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="label-mono text-[9px] text-text-faint">MONTHLY BUDGET / {{ stats.budget.month }}</p>
          <p class="font-mono text-xs tabular-nums" :class="stats.budget.over_budget ? 'text-danger' : 'text-text-soft'">
            {{ formatUsd(stats.budget.month_cost_usd) }} / {{ formatUsd(stats.budget.monthly_budget_usd, 2) }}
          </p>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-black/20" data-role="token-budget-track">
          <span
            class="block h-full rounded-full transition-[width] duration-500"
            :class="stats.budget.over_budget ? 'bg-danger' : 'bg-success'"
            :style="{ width: `${budgetWidth}%` }"
          />
        </div>
      </section>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,0.75fr)]">
        <TokenTrendChart :daily="stats.daily" />

        <section class="grid content-start gap-3 rounded-[20px] border border-border/70 bg-black/10 p-4" data-role="model-usage-ranking">
          <header class="flex items-center justify-between gap-3">
            <div>
              <p class="label-mono text-[10px] text-warning">MODEL MIX</p>
              <h3 class="mt-1 text-sm font-bold text-text">模型用量排行</h3>
            </div>
            <span class="font-mono text-[10px] text-text-faint">{{ sortedModels.length }} MODELS</span>
          </header>

          <div v-if="sortedModels.length" class="grid gap-3">
            <article
              v-for="model in sortedModels"
              :key="model.model_name"
              class="grid gap-2 rounded-[14px] border border-border/60 bg-panel/55 p-3"
              data-role="model-usage-row"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <strong class="block truncate text-xs text-text">{{ model.model_name }}</strong>
                  <span class="font-mono text-[9px] text-text-faint">{{ model.call_count }} calls · {{ formatCompact(model.total_tokens) }} tokens</span>
                </div>
                <span class="font-mono text-xs text-warning">{{ modelShare(model) }}%</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-black/20">
                <span class="block h-full rounded-full bg-[linear-gradient(90deg,var(--warning),var(--accent))]" :style="{ width: `${modelShare(model)}%` }" />
              </div>
              <span class="justify-self-end font-mono text-[9px]" :class="model.cost_available ? 'text-success' : 'text-text-faint'">
                {{ model.cost_available ? formatUsd(model.cost_usd) : '成本未配置' }}
              </span>
            </article>
          </div>
          <p v-else class="rounded-[14px] border border-dashed border-border/60 px-3 py-8 text-center text-sm text-text-soft">
            暂无模型用量记录
          </p>
        </section>
      </div>

      <div v-if="sortedOperations.length" class="flex flex-wrap gap-2">
        <span
          v-for="operation in sortedOperations"
          :key="operation.operation_type"
          class="rounded-full border border-border/70 bg-panel/50 px-3 py-1 font-mono text-[10px] text-text-faint"
        >
          {{ operation.operation_type }} · {{ formatCompact(operation.total_tokens) }}
        </span>
      </div>
    </div>
  </SectionCard>
</template>
