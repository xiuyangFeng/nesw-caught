<script setup lang="ts">
import StaleBadge from '../common/StaleBadge.vue';

defineProps<{
  status: {
    label: string;
    detail: string;
    tone: 'success' | 'warning' | 'danger' | 'default';
  };
  stale: boolean;
}>();
</script>

<template>
  <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
    <div>
      <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-accent font-mono">Secondary Overview</p>
      <h1 class="page-title">Dashboard</h1>
      <p class="page-subtitle">
        Overview Snapshot：为最新事件页提供连接状态、主题舆情和自选股异动的多维交互控制台。
      </p>
    </div>
    <div class="flex items-center gap-2 self-start">
      <span
        class="dashboard-status-badge"
        :class="`dashboard-status-badge--${status.tone}`"
        data-role="dashboard-status-badge"
      >
        <span class="dashboard-status-badge__dot" />
        <span>{{ status.label }}</span>
        <small>{{ status.detail }}</small>
      </span>
      <StaleBadge :stale="stale" label="全局数据" />
    </div>
  </header>
</template>

<style scoped>
.dashboard-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.035);
  padding: 7px 10px;
  font-size: 11px;
  line-height: 1;
  color: var(--muted);
}

.dashboard-status-badge small {
  color: var(--text-faint);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.dashboard-status-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.04);
}

.dashboard-status-badge--success {
  color: var(--success);
}

.dashboard-status-badge--warning {
  color: var(--warning);
}

.dashboard-status-badge--danger {
  color: var(--danger);
}

.dashboard-status-badge--default {
  color: var(--muted);
}
</style>
