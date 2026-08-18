<script setup lang="ts">
import { onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantReportCard } from '../types/api';

const windowDays = ref('30d');
const card = ref<QuantReportCard | null>(null);
const error = ref<string | null>(null);

const sleeveLabels: Record<string, string> = {
  event_catalyst: '事件/催化',
  trend_flow: '趋势/资金',
  fundamental_revalue: '基本面重估',
};

async function load() {
  try {
    const response = await apiClient.getQuantReportCard(windowDays.value);
    card.value = response.data;
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '成绩单加载失败';
  }
}

function funnelCount(key: string, field: 'qualified' | 'watch'): number {
  const row = card.value?.sleeves?.[key];
  const value = row?.[field];
  return typeof value === 'number' ? value : 0;
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-report-card-view">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">成绩单</h1>
        <p class="page-subtitle">按 sleeve 回填漏斗；财务未覆盖前不宣称超额收益。</p>
      </div>
      <select
        v-model="windowDays"
        class="rounded-md border border-border bg-panel px-3 py-1.5 text-sm"
        data-role="desk-report-window"
        @change="load"
      >
        <option value="7d">7d</option>
        <option value="30d">30d</option>
        <option value="90d">90d</option>
      </select>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="Funnel" title="Sleeve 漏斗" :subtitle="card?.note ?? ''">
      <ul class="grid gap-2 text-sm" data-role="desk-report-funnel">
        <li v-for="(label, key) in sleeveLabels" :key="key">
          {{ label }} · 合格 {{ funnelCount(key, 'qualified') }} · 观察 {{ funnelCount(key, 'watch') }}
        </li>
      </ul>
      <p class="mt-3 text-xs text-muted">样本 {{ card?.sample_size ?? 0 }} · 窗口 {{ card?.window ?? windowDays }}</p>
    </SectionCard>
  </div>
</template>
