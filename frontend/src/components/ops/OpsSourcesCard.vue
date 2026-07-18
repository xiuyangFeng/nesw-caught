<script setup lang="ts">
import type { OpsSource } from '../../types/api';
import { latencyLabel, ratePct, sourceTone, timeLabel } from './opsFormat';

defineProps<{
  sources: OpsSource[];
}>();
</script>

<template>
  <!-- News sources -->
  <section class="surface ops-card" data-role="ops-sources">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Ingestion</p>
        <h2 class="ops-card-title">新闻源健康</h2>
      </div>
      <span class="num ops-count">{{ sources.length }}</span>
    </div>
    <div v-if="sources.length === 0" class="ops-empty">暂无新闻源记录</div>
    <div v-else class="ops-scroller grid gap-2">
      <article
        v-for="source in sources"
        :key="`${source.source_name}-${source.market}`"
        class="ops-row"
        data-role="ops-source-row"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="ops-mini-dot" :class="`ops-mini-dot--${sourceTone(source.consecutive_failures, source.is_disabled)}`" />
            <strong class="truncate text-[13px]">{{ source.source_name }}</strong>
            <span class="text-[10px] uppercase tracking-[0.14em] text-warning">{{ source.market }}</span>
            <span
              v-if="source.last_status"
              class="pill ops-status-pill"
              :data-status="source.last_status"
            >{{ source.last_status }}</span>
            <span v-if="source.is_disabled" class="pill danger ops-pill-crit">disabled</span>
          </div>
          <div class="ops-meta">
            成功率 <span class="num">{{ ratePct(source.success_rate) }}</span> · 连败 <span class="num">{{ source.consecutive_failures }}</span> · 时延 <span class="num">{{ latencyLabel(source.avg_latency_ms) }}</span> · {{ source.source_type }}
          </div>
          <div class="ops-diagnostics" data-role="ops-source-diagnostics">
            <span v-if="source.last_http_status != null">HTTP <span class="num">{{ source.last_http_status }}</span></span>
            <span>解析 <span class="num">{{ source.last_fetched_count ?? 0 }}</span></span>
            <span>入库 <span class="num">{{ source.last_inserted_count ?? 0 }}</span></span>
            <span>空批 <span class="num">{{ source.consecutive_empty_batches ?? 0 }}</span></span>
          </div>
          <div v-if="source.last_error" class="ops-error-line" data-role="ops-source-error">
            {{ source.last_error }}
          </div>
        </div>
        <div class="ops-row-aside">
          <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
          <span class="num text-[11px] text-muted">{{ timeLabel(source.last_success_at) }}</span>
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

.ops-scroller {
  max-height: 22rem;
  overflow-y: auto;
  padding-right: 4px;
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

.ops-diagnostics {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 0 8px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--muted);
}

.ops-diagnostics > span + span::before {
  content: '· ';
  color: var(--text-faint);
}

.ops-error-line {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.4;
  color: var(--danger);
  word-break: break-word;
}

.pill.ops-status-pill {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: var(--panel-strong);
  color: var(--text-soft);
}

.pill.ops-status-pill[data-status='ok'],
.pill.ops-status-pill[data-status='not_modified'] {
  background: var(--success-soft);
  color: var(--success);
}

.pill.ops-status-pill[data-status='empty'] {
  background: var(--warning-soft);
  color: var(--warning);
}

.pill.ops-status-pill[data-status='parse_error'],
.pill.ops-status-pill[data-status='http_error'] {
  background: var(--danger-soft);
  color: var(--danger);
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
