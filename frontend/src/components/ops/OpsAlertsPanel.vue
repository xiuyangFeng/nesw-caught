<script setup lang="ts">
import type { OpsAlert } from '../../types/api';

defineProps<{
  alerts: OpsAlert[];
}>();
</script>

<template>
  <!-- 顶部醒目告警区 -->
  <section class="grid gap-2.5" data-role="ops-alerts">
    <div
      v-if="alerts.length === 0"
      class="ops-alert ops-alert--ok"
      data-role="ops-alert-empty"
    >
      <span class="ops-signal-dot ops-signal-dot--ok" />
      <div class="min-w-0">
        <strong class="block text-[13px]">All systems nominal</strong>
        <span class="text-[12px] text-muted">当前无触发阈值的告警。</span>
      </div>
    </div>
    <div
      v-for="(alert, index) in alerts"
      :key="`${alert.code}-${alert.subject}-${index}`"
      class="ops-alert"
      :class="`ops-alert--${alert.level}`"
      data-role="ops-alert"
    >
      <span class="ops-signal-dot" :class="`ops-signal-dot--${alert.level}`" />
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <span class="ops-alert-level" :class="`ops-alert-level--${alert.level}`">{{ alert.level }}</span>
          <code class="ops-alert-code">{{ alert.code }}</code>
          <span class="text-[11px] uppercase tracking-[0.12em] text-text-faint">{{ alert.subject }}</span>
        </div>
        <p class="m-0 mt-1 text-[13px] leading-5 text-text-soft">{{ alert.message }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* --- 呼吸灯信号点（与现有 shadow-signal 风格一致的辉光） --- */
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

/* --- 告警卡片 --- */
.ops-alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.025);
  padding: 12px 14px;
}

.ops-alert--ok {
  border-color: rgba(57, 200, 132, 0.24);
  background: rgba(57, 200, 132, 0.06);
}

.ops-alert--warning {
  border-color: rgba(255, 159, 47, 0.34);
  background: linear-gradient(90deg, rgba(255, 159, 47, 0.1) 0%, rgba(255, 159, 47, 0.02) 60%, rgba(255, 255, 255, 0.025) 100%);
}

.ops-alert--critical {
  border-color: rgba(255, 111, 134, 0.4);
  background: linear-gradient(90deg, rgba(255, 111, 134, 0.12) 0%, rgba(255, 111, 134, 0.03) 60%, rgba(255, 255, 255, 0.025) 100%);
}

.ops-alert-level {
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.ops-alert-level--warning {
  background: rgba(255, 159, 47, 0.16);
  color: #ffb264;
}

.ops-alert-level--critical {
  background: rgba(255, 111, 134, 0.16);
  color: #ff8a9c;
}

.ops-alert-code {
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  color: var(--system);
}
</style>
