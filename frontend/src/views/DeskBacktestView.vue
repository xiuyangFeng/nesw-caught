<script setup lang="ts">
import { ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantBacktest } from '../types/api';

const DEFAULT_DSL = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 1 }],
};

const dslText = ref(JSON.stringify(DEFAULT_DSL, null, 2));
const report = ref<QuantBacktest | null>(null);
const error = ref<string | null>(null);
const running = ref(false);

async function handleRun() {
  running.value = true;
  error.value = null;
  try {
    const dsl = JSON.parse(dslText.value) as Record<string, unknown>;
    const response = await apiClient.runQuantBacktest({ name: 'lab', dsl, is_active: false });
    report.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '回测失败或 DSL 无法解析';
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="grid gap-4" data-role="desk-backtest-view">
    <header>
      <h1 class="page-title">回测实验室</h1>
      <p class="page-subtitle">自研 walk-forward；探索性回测不得显示 qualified，也不能承诺收益。</p>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="Lab" title="运行 walk-forward">
      <textarea
        v-model="dslText"
        class="min-h-[160px] w-full rounded-md border border-border bg-panel p-3 font-mono text-xs"
        data-role="desk-backtest-dsl"
      />
      <button
        type="button"
        class="mt-3 rounded-md border border-accent px-3 py-1.5 text-sm text-accent"
        :disabled="running"
        data-role="desk-backtest-run"
        @click="handleRun"
      >
        {{ running ? '回测中…' : '运行回测' }}
      </button>
    </SectionCard>
    <SectionCard v-if="report" eyebrow="Report" title="回测报告" :subtitle="report.note ?? ''">
      <dl class="grid gap-2 text-sm" data-role="desk-backtest-report">
        <div>状态 {{ report.status }}</div>
        <div>探索性 {{ report.exploratory ? '是' : '否' }}</div>
        <div>qualified {{ report.qualified ? '是' : '否（不得晋级）' }}</div>
      </dl>
      <pre class="mt-3 overflow-auto rounded-md bg-panel-soft p-3 text-xs text-muted">{{ JSON.stringify(report.metrics, null, 2) }}</pre>
    </SectionCard>
  </div>
</template>
