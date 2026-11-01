<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { apiClient } from '../../api/client';
import type { AiFunnelInactiveReason, AiFunnelStatus, AiFunnelUsage } from '../../types/api';
import { formatMarketTime } from '../../utils/time';

const status = ref<AiFunnelStatus | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const REASON_TEXT: Record<AiFunnelInactiveReason, string> = {
  disabled: '漏斗已关闭（AI_FUNNEL_ENABLED=false）',
  no_default_model: '未设置默认模型：在下方添加 gpt-6.1-terra 并设为默认',
  over_budget: '本月费用已达预算，已暂停',
  budget_unpriced: '设了月度预算但默认模型没填单价，无法核算费用，已暂停',
  quota_exhausted: '今日精读额度已用完，提醒暂时回退关键词规则',
  worker_not_running: '漏斗 worker 未运行',
};

const OPERATION_LABELS: Record<string, string> = {
  ai_screen: '粗筛',
  ai_impact: '精读',
  sector_infer: '板块推断',
};
const OPERATION_ORDER = ['ai_screen', 'ai_impact', 'sector_infer'];

const reasonText = computed(() => {
  const reason = status.value?.inactive_reason;
  return reason ? REASON_TEXT[reason] ?? reason : null;
});

const modelText = computed(() => {
  const current = status.value;
  if (!current) {
    return '—';
  }
  const { model_display_name: display, model_name: name } = current;
  if (display && name && display !== name) {
    return `${display}（${name}）`;
  }
  return display || name || '未设置';
});

const usageRows = computed<AiFunnelUsage[]>(() => {
  const usage = status.value?.usage ?? [];
  const byType = new Map(usage.map((row) => [row.operation_type, row]));
  const ordered = OPERATION_ORDER.map(
    (type) =>
      byType.get(type) ?? { operation_type: type, calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0 },
  );
  const extra = usage.filter((row) => !OPERATION_ORDER.includes(row.operation_type));
  return [...ordered, ...extra];
});

function operationLabel(type: string) {
  return OPERATION_LABELS[type] ?? type;
}

function formatUsd(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined) {
    return '—';
  }
  return `$${value.toFixed(digits)}`;
}

function formatTokens(value: number) {
  return value.toLocaleString('en-US');
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.getAiFunnelStatus();
    status.value = response.data ?? null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'AI 漏斗状态加载失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <section class="surface grid gap-3 rounded-lg border border-border px-5 py-4" data-role="ai-funnel-status">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="label-mono text-[10px] text-ai">AI FUNNEL</p>
        <h2 class="mt-1 text-lg font-bold text-text">AI 新闻漏斗</h2>
      </div>
      <button
        type="button"
        class="rounded-full border border-border px-3 py-1 text-xs text-text-soft transition hover:text-text disabled:opacity-50"
        :disabled="loading"
        data-role="ai-funnel-refresh"
        @click="load"
      >
        {{ loading ? '刷新中…' : '刷新' }}
      </button>
    </header>

    <p v-if="error" class="m-0 text-sm text-danger" data-role="ai-funnel-error">{{ error }}</p>
    <p v-else-if="!status && loading" class="m-0 text-sm text-text-faint">加载漏斗状态…</p>
    <template v-else-if="status">
      <div class="flex flex-wrap items-center gap-2 text-sm" data-role="ai-funnel-state">
        <span
          class="rounded-full border px-2.5 py-0.5 text-xs font-semibold"
          :class="status.active ? 'border-success/40 bg-success/10 text-success' : 'border-warning/40 bg-warning/10 text-warning'"
        >
          {{ status.active ? '在线' : '未运行' }}
        </span>
        <span v-if="!status.active && reasonText" class="text-text-soft" data-role="ai-funnel-reason">{{ reasonText }}</span>
        <span class="ml-auto text-xs text-text-faint">
          模型：<span class="text-text" data-role="ai-funnel-model">{{ modelText }}</span>
        </span>
      </div>

      <div class="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-text-soft tabular-nums" data-role="ai-funnel-today">
        <span>今日 粗筛 {{ status.today.screened }}（失败 {{ status.today.screen_errors }}）</span>
        <span>精读 {{ status.today.analyzed }} / {{ status.today.analysis_daily_limit }}（失败 {{ status.today.analysis_errors }}）</span>
        <span>影响 {{ status.today.impacts }}</span>
        <span>今日费用 {{ formatUsd(status.today.cost_usd) }}</span>
        <span :class="status.over_budget ? 'text-danger' : ''" data-role="ai-funnel-month">
          本月 {{ formatUsd(status.month_cost_usd) }} / 预算
          {{ status.monthly_budget_usd === null || status.monthly_budget_usd === undefined ? '未设置' : formatUsd(status.monthly_budget_usd, 2) }}
        </span>
      </div>

      <table class="w-full text-left text-xs" data-role="ai-funnel-usage">
        <thead class="text-text-faint">
          <tr>
            <th class="py-1 font-normal">今日环节</th>
            <th class="py-1 text-right font-normal">调用</th>
            <th class="py-1 text-right font-normal">输入 tokens</th>
            <th class="py-1 text-right font-normal">输出 tokens</th>
            <th class="py-1 text-right font-normal">费用</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in usageRows"
            :key="row.operation_type"
            class="tabular-nums text-text"
            data-role="ai-funnel-usage-row"
          >
            <td class="py-1">{{ operationLabel(row.operation_type) }}</td>
            <td class="py-1 text-right">{{ row.calls }}</td>
            <td class="py-1 text-right">{{ formatTokens(row.prompt_tokens) }}</td>
            <td class="py-1 text-right">{{ formatTokens(row.completion_tokens) }}</td>
            <td class="py-1 text-right">{{ formatUsd(row.cost_usd) }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="status.last_error?.message" class="m-0 text-xs text-danger" data-role="ai-funnel-last-error">
        最近错误（{{ formatMarketTime(status.last_error.at, 'cn') }}）：{{ status.last_error.message }}
      </p>
    </template>
  </section>
</template>
