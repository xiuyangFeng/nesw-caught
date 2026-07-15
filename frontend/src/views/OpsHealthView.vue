<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { apiClient } from '../api/client';
import OpsAlertsPanel from '../components/ops/OpsAlertsPanel.vue';
import OpsLlmUsageCard from '../components/ops/OpsLlmUsageCard.vue';
import OpsSourcesCard from '../components/ops/OpsSourcesCard.vue';
import OpsSystemStatusCard from '../components/ops/OpsSystemStatusCard.vue';
import OpsWorkersCard from '../components/ops/OpsWorkersCard.vue';
import OpsXSourcesCard from '../components/ops/OpsXSourcesCard.vue';
import { timeLabel } from '../components/ops/opsFormat';
import type { OpsAlert, OpsHealth } from '../types/api';

// 每 15s 轮询一次健康看板。
const POLL_INTERVAL_MS = 15_000;

const health = ref<OpsHealth | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const lastLoadedAt = ref<string | null>(null);
let pollHandle: ReturnType<typeof setInterval> | null = null;
let disposed = false;

async function loadHealth() {
  loading.value = true;
  try {
    const response = await apiClient.getOpsHealth();
    if (disposed) {
      return;
    }
    health.value = response.data;
    error.value = null;
    lastLoadedAt.value = new Date().toISOString();
  } catch {
    error.value = '健康看板加载失败，请检查后端服务';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  disposed = false;
  void loadHealth();
  pollHandle = setInterval(() => {
    void loadHealth();
  }, POLL_INTERVAL_MS);
});

onBeforeUnmount(() => {
  disposed = true;
  if (pollHandle !== null) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
});

const overall = computed(() => health.value?.overall_status ?? 'ok');
const alerts = computed<OpsAlert[]>(() => health.value?.alerts ?? []);
const criticalCount = computed(() => alerts.value.filter((a) => a.level === 'critical').length);
const warningCount = computed(() => alerts.value.filter((a) => a.level === 'warning').length);

const overallBadge = computed(() => {
  if (overall.value === 'critical') {
    return { label: 'CRITICAL', tone: 'critical' as const, detail: `${criticalCount.value} 项严重` };
  }
  if (overall.value === 'warning') {
    return { label: 'WARNING', tone: 'warning' as const, detail: `${warningCount.value} 项告警` };
  }
  return { label: 'NOMINAL', tone: 'ok' as const, detail: '各子系统正常' };
});
</script>

<template>
  <div class="grid gap-4" data-role="ops-health-view">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Operations</p>
        <h1 class="page-title">System Health</h1>
        <p class="page-subtitle">
          统一运维看板：按需聚合后台 worker、新闻源 / X 源健康、近 24h LLM 用量、事件层与数据库体积，并给出结构化告警。每 15s 自动刷新。
        </p>
      </div>
      <div class="flex items-center gap-2 self-start">
        <span
          class="ops-overall-badge"
          :class="`ops-overall-badge--${overallBadge.tone}`"
          data-role="ops-overall-badge"
        >
          <span class="ops-signal-dot" :class="`ops-signal-dot--${overallBadge.tone}`" />
          <span>{{ overallBadge.label }}</span>
          <small>{{ overallBadge.detail }}</small>
        </span>
        <button
          type="button"
          class="ops-refresh-btn"
          :disabled="loading"
          data-role="ops-refresh"
          @click="loadHealth"
        >
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="ops-error" data-role="ops-error">{{ error }}</p>

    <OpsAlertsPanel :alerts="alerts" />

    <!-- 分区网格 -->
    <div class="grid gap-4 xl:grid-cols-2" data-role="ops-sections">
      <OpsWorkersCard :workers="health?.workers ?? []" />
      <OpsLlmUsageCard :llm-usage="health?.llm_usage ?? null" />
      <OpsSourcesCard :sources="health?.sources ?? []" />

      <!-- X sources + Event bus + Database 合并到右列 -->
      <div class="grid gap-4">
        <OpsXSourcesCard :x-sources="health?.x_sources ?? []" />
        <OpsSystemStatusCard :event-bus="health?.event_bus ?? null" :database="health?.database ?? null" />
      </div>
    </div>

    <footer class="text-[11px] uppercase tracking-[0.12em] text-text-faint" data-role="ops-footer">
      最近刷新 {{ lastLoadedAt ? timeLabel(lastLoadedAt) : '--' }} · 自动轮询 15s
    </footer>
  </div>
</template>

<style scoped>
.ops-overall-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.035);
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}

.ops-overall-badge small {
  color: var(--text-faint);
  font-size: 10px;
  letter-spacing: 0.06em;
}

.ops-overall-badge--ok {
  color: #7ed89e;
  border-color: rgba(57, 200, 132, 0.28);
}

.ops-overall-badge--warning {
  color: #ffb264;
  border-color: rgba(255, 159, 47, 0.34);
}

.ops-overall-badge--critical {
  color: #ff8a9c;
  border-color: rgba(255, 111, 134, 0.36);
}

.ops-refresh-btn {
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.04);
  padding: 7px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
  transition: border-color 150ms ease, background 150ms ease;
}

.ops-refresh-btn:hover:not(:disabled) {
  border-color: rgba(83, 194, 255, 0.4);
  background: rgba(83, 194, 255, 0.08);
}

.ops-refresh-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.ops-error {
  margin: 0;
  border-radius: 12px;
  border: 1px solid rgba(255, 111, 134, 0.34);
  background: rgba(255, 111, 134, 0.08);
  padding: 10px 12px;
  font-size: 13px;
  color: #ff8a9c;
}

/* --- 呼吸灯信号点（顶部总体状态徽标复用；与现有 shadow-signal 风格一致的辉光） --- */
.ops-signal-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--muted);
}

.ops-signal-dot--ok {
  background: #39c884;
  box-shadow: 0 0 10px rgba(57, 200, 132, 0.5);
  animation: ops-breathe-ok 2.4s ease-in-out infinite;
}

.ops-signal-dot--warning {
  background: #ff9f2f;
  box-shadow: 0 0 12px rgba(255, 159, 47, 0.55);
  animation: ops-breathe-warn 1.6s ease-in-out infinite;
}

.ops-signal-dot--critical {
  background: #ff6f86;
  box-shadow: 0 0 14px rgba(255, 111, 134, 0.65);
  animation: ops-breathe-crit 1s ease-in-out infinite;
}

@keyframes ops-breathe-ok {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}

@keyframes ops-breathe-warn {
  0%, 100% { opacity: 0.5; transform: scale(0.94); }
  50% { opacity: 1; transform: scale(1.06); }
}

@keyframes ops-breathe-crit {
  0%, 100% { opacity: 0.45; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.12); }
}
</style>
