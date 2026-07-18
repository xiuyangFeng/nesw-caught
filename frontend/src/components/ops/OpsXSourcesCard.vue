<script setup lang="ts">
import type { OpsXSource } from '../../types/api';
import { latencyLabel, ratePct, sourceTone, timeLabel } from './opsFormat';

defineProps<{
  xSources: OpsXSource[];
}>();
</script>

<template>
  <section class="surface ops-card" data-role="ops-x-sources">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Social</p>
        <h2 class="ops-card-title">X 数据源</h2>
      </div>
      <span class="num ops-count">{{ xSources.length }}</span>
    </div>
    <div v-if="xSources.length === 0" class="ops-empty">暂无 X 源记录</div>
    <div v-else class="grid gap-2">
      <article
        v-for="x in xSources"
        :key="x.provider_name"
        class="ops-row"
        data-role="ops-x-source-row"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="ops-mini-dot" :class="`ops-mini-dot--${sourceTone(x.consecutive_failures, false)}`" />
            <strong class="truncate text-[13px]">{{ x.provider_name }}</strong>
          </div>
          <div class="ops-meta">
            成功率 <span class="num">{{ ratePct(x.success_rate) }}</span> · 连败 <span class="num">{{ x.consecutive_failures }}</span> · 时延 <span class="num">{{ latencyLabel(x.avg_latency_ms) }}</span>
          </div>
          <div v-if="x.last_error" class="ops-error-line">最近错误：{{ x.last_error }}</div>
        </div>
        <div class="ops-row-aside">
          <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
          <span class="num text-[11px] text-muted">{{ timeLabel(x.last_success_at) }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.ops-card {
  border-radius: 18px;
  padding: 16px 16px;
}

.ops-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ops-eyebrow {
  margin: 0 0 2px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--warning);
}

.ops-card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.ops-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  padding: 4px 10px;
}

.ops-empty {
  border-radius: 12px;
  border: 1px dashed var(--border);
  padding: 14px;
  text-align: center;
  font-size: 12px;
  color: var(--text-faint);
}

.ops-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--panel-soft);
  padding: 10px 12px;
}

.ops-row-aside {
  display: grid;
  gap: 2px;
  text-align: right;
  flex-shrink: 0;
}

.ops-meta {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--muted);
}

.ops-error-line {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--danger);
  word-break: break-word;
}

.ops-mini-dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--muted);
}

.ops-mini-dot--ok { background: var(--success); box-shadow: 0 0 6px color-mix(in srgb, var(--success) 50%, transparent); }
.ops-mini-dot--warning { background: var(--warning); box-shadow: 0 0 6px color-mix(in srgb, var(--warning) 50%, transparent); }
.ops-mini-dot--critical { background: var(--danger); box-shadow: 0 0 6px color-mix(in srgb, var(--danger) 55%, transparent); }
.ops-mini-dot--neutral { background: var(--system); box-shadow: 0 0 6px color-mix(in srgb, var(--system) 40%, transparent); }
</style>
