<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantDataStatus } from '../types/api';

const tab = ref<'runs' | 'data' | 'ai' | 'decisions'>('data');
const status = ref<QuantDataStatus | null>(null);
const error = ref<string | null>(null);

const coverageLabel = computed(() => {
  const pct = status.value?.coverage_pct;
  return pct == null ? '—' : `${pct}%`;
});

onMounted(async () => {
  try {
    const response = await apiClient.getQuantDataStatus();
    status.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据健康加载失败';
  }
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-ops-view">
    <header>
      <h1 class="page-title">运行中心</h1>
      <p class="page-subtitle">量化域业务运行：数据覆盖、流水线与 AI 审计。全站基础设施仍在系统健康页。</p>
    </header>

    <div class="flex flex-wrap gap-2" data-role="desk-ops-tabs">
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'runs' ? 'border-accent text-accent' : 'border-border text-muted'" @click="tab = 'runs'">流水线 Runs</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'data' ? 'border-accent text-accent' : 'border-border text-muted'" data-role="desk-ops-tab-data" @click="tab = 'data'">数据健康</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'ai' ? 'border-accent text-accent' : 'border-border text-muted'" @click="tab = 'ai'">AI 审计</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'decisions' ? 'border-accent text-accent' : 'border-border text-muted'" @click="tab = 'decisions'">决策日志</button>
    </div>

    <p v-if="error" class="text-sm text-danger">{{ error }}</p>

    <SectionCard v-if="tab === 'data'" eyebrow="Coverage" title="数据健康" subtitle="独立行情库 coverage；未回填时为 0 是预期空态">
      <dl class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm" data-role="desk-ops-data-health">
        <div>
          <dt class="text-muted">覆盖率</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ coverageLabel }}</dd>
        </div>
        <div>
          <dt class="text-muted">日线条数</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.daily_bar_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">已回填标的</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.symbol_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">资金流行数</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.fund_flow_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">最近交易日</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.last_trade_date ?? '—' }}</dd>
        </div>
        <div class="sm:col-span-2">
          <dt class="text-muted">说明</dt>
          <dd class="mt-1 text-text">{{ status?.note ?? '加载中' }}</dd>
        </div>
      </dl>
    </SectionCard>

    <SectionCard v-else :title="tab === 'runs' ? '流水线 Runs' : tab === 'ai' ? 'AI 审计' : '决策日志'" subtitle="后续 Phase 接入阶段日志与审计表">
      <p class="text-sm text-muted">本期仅数据健康 Tab 可读。其余视图将在 Phase 2/3 接入。</p>
    </SectionCard>
  </div>
</template>
