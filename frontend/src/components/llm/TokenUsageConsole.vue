<script setup lang="ts">
import SectionCard from '../common/SectionCard.vue';
import TokenTrendChart from './TokenTrendChart.vue';
import type { TokenStats } from './types';

defineProps<{
  stats: TokenStats;
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

// 将美元金额格式化为定长字符串；null/undefined 显示占位符。
function formatUsd(value: number | null | undefined, digits = 4): string {
  return value != null ? `$${value.toFixed(digits)}` : '—';
}

function formatPercent(ratio: number | null | undefined): string {
  return ratio != null ? `${Math.round(ratio * 100)}%` : '—';
}
</script>

<template>
  <SectionCard title="模型额度审计控制台 (LLM Token Usage Console)" subtitle="系统运行过程中产生的 Token 消耗审计与成本估算">
    <template #action>
      <button
        class="rounded-lg bg-white/[0.05] hover:bg-white/[0.1] px-2.5 py-1 text-xs text-text-faint hover:text-text transition-colors"
        type="button"
        :disabled="loading"
        @click="emit('refresh')"
      >
        {{ loading ? '刷新中...' : '🔄 刷新审计' }}
      </button>
    </template>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mt-2">
      <!-- Metric 1: Total Tokens -->
      <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
        <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Total Tokens</div>
        <div class="text-xl font-bold text-text-faint font-mono mt-1 group-hover:text-text transition-colors">
          {{ stats.overall.total_tokens.toLocaleString() }}
        </div>
        <div class="text-[10px] text-text-faint mt-1 flex justify-between">
          <span>In: {{ stats.overall.prompt_tokens.toLocaleString() }}</span>
          <span>Out: {{ stats.overall.completion_tokens.toLocaleString() }}</span>
        </div>
        <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-500/80 shadow-[0_0_8px_#3b82f6]" />
      </div>

      <!-- Metric 2: Real Cost (基于各模型配置单价换算) -->
      <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
        <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Real Cost (USD)</div>
        <div class="text-xl font-bold text-emerald-400 font-mono mt-1">
          {{ stats.overall?.cost_available ? formatUsd(stats.overall?.cost_usd) : '—' }}
        </div>
        <div class="text-[10px] text-text-faint mt-1">
          {{ stats.overall?.cost_available ? '基于各模型配置单价换算真实花费' : '未配置模型单价，无法换算' }}
        </div>
        <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-emerald-500/80 shadow-[0_0_8px_#10b981]" />
      </div>

      <!-- Metric 3: Active Models Stats -->
      <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
        <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Active Providers</div>
        <div class="text-xl font-bold text-purple-400 font-mono mt-1">
          {{ stats.models.length }} <span class="text-xs text-text-faint">Models</span>
        </div>
        <div class="text-[10px] text-text-faint mt-1 truncate">
          已触发 {{ (stats.models || []).reduce((acc, m) => acc + (m.call_count || 0), 0) }} 次接口请求
        </div>
        <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-purple-500/80 shadow-[0_0_8px_#a855f7]" />
      </div>

      <!-- Metric 4: Top Model -->
      <div class="rounded-xl border border-border/60 bg-white/[0.01] p-4 flex flex-col justify-between h-24 shadow-sm relative overflow-hidden group">
        <div class="text-[10px] uppercase tracking-wider text-muted font-mono">Top Pick Model</div>
        <div class="text-xs font-bold text-text truncate mt-1.5">
          {{ stats.models?.[0]?.model_name || 'N/A' }}
        </div>
        <div class="text-[10px] text-text-faint mt-1">
          占比: {{ stats.overall?.total_tokens ? Math.round((stats.models?.[0]?.total_tokens || 0) / stats.overall.total_tokens * 100) : 0 }}%
        </div>
        <div class="absolute left-0 top-0 bottom-0 w-0.5 bg-amber-500/80 shadow-[0_0_8px_#f59e0b]" />
      </div>
    </div>

    <!-- 本月累计花费 vs 月度预算：超预算高亮告警 -->
    <div
      v-if="stats.budget?.budget_available"
      class="mt-4 rounded-xl border p-3 flex flex-wrap items-center justify-between gap-3 text-xs"
      :class="stats.budget?.over_budget
        ? 'border-red-500/60 bg-red-500/10 text-red-300'
        : 'border-emerald-500/40 bg-emerald-500/[0.06] text-text-faint'"
      data-testid="llm-budget-banner"
    >
      <div class="flex items-center gap-2 font-mono">
        <span class="uppercase tracking-wider text-[10px] text-muted">本月累计 vs 预算 ({{ stats.budget?.month }})</span>
        <span class="text-sm font-bold" :class="stats.budget?.over_budget ? 'text-red-400' : 'text-emerald-400'">
          {{ formatUsd(stats.budget?.month_cost_usd) }} / {{ formatUsd(stats.budget?.monthly_budget_usd, 2) }}
        </span>
        <span class="text-[10px] text-text-faint">({{ formatPercent(stats.budget?.usage_ratio) }})</span>
      </div>
      <span v-if="stats.budget?.over_budget" class="font-bold text-red-400">⚠ 已超出月度预算</span>
      <span v-else class="text-emerald-400/80">预算内</span>
    </div>

    <!-- Token Trend Chart Section -->
    <TokenTrendChart :daily="stats.daily" />

    <!-- Detail rows showing model stats -->
    <div v-if="stats.models.length > 0" class="mt-4 border border-border/40 bg-black/10 rounded-xl p-3 overflow-hidden text-xs">
      <div class="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted font-mono border-b border-border/30 pb-2 mb-2">
        <span>Model Name</span>
        <div class="flex gap-8">
          <span class="w-16 text-right">Calls</span>
          <span class="w-20 text-right">Total Tokens</span>
          <span class="w-20 text-right">Cost ($)</span>
        </div>
      </div>
      <div class="space-y-2">
        <div v-for="m in stats.models" :key="m.model_name" class="flex items-center justify-between font-mono text-text-faint">
          <span class="truncate pr-4">{{ m.model_name }}</span>
          <div class="flex gap-8 shrink-0">
            <span class="w-16 text-right">{{ m.call_count }}</span>
            <span class="w-20 text-right text-text">{{ m.total_tokens.toLocaleString() }}</span>
            <span class="w-20 text-right" :class="m.cost_available ? 'text-emerald-400' : 'text-text-faint'">
              {{ m.cost_available ? formatUsd(m.cost_usd) : '—' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </SectionCard>
</template>
