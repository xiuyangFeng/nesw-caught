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
  background: var(--success);
  box-shadow: 0 0 10px color-mix(in srgb, var(--success) 50%, transparent);
  animation: ops-breathe-ok 2.4s ease-in-out infinite;
}

.ops-signal-dot--warning {
  background: var(--warning);
  box-shadow: 0 0 12px color-mix(in srgb, var(--warning) 55%, transparent);
  animation: ops-breathe-warn 1.6s ease-in-out infinite;
}

.ops-signal-dot--critical {
  background: var(--danger);
  box-shadow: 0 0 14px color-mix(in srgb, var(--danger) 65%, transparent);
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
  background: var(--panel);
  padding: 12px 14px;
}

.ops-alert--ok {
  border-color: color-mix(in srgb, var(--success) 24%, transparent);
  background: color-mix(in srgb, var(--success) 6%, transparent);
}

.ops-alert--warning {
  border-color: color-mix(in srgb, var(--warning) 34%, transparent);
  background: linear-gradient(90deg, color-mix(in srgb, var(--warning) 10%, transparent) 0%, color-mix(in srgb, var(--warning) 2%, transparent) 60%, var(--panel) 100%);
}

.ops-alert--critical {
  border-color: color-mix(in srgb, var(--danger) 40%, transparent);
  background: linear-gradient(90deg, color-mix(in srgb, var(--danger) 12%, transparent) 0%, color-mix(in srgb, var(--danger) 3%, transparent) 60%, var(--panel) 100%);
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
  background: color-mix(in srgb, var(--warning) 16%, transparent);
  color: var(--warning);
}

.ops-alert-level--critical {
  background: color-mix(in srgb, var(--danger) 16%, transparent);
  color: var(--danger);
}

.ops-alert-code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--system);
}
</style>
