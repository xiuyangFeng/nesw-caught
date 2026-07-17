<script setup lang="ts">
import type { OpsSource } from '../../types/api';
import { latencyLabel, ratePct, sourceTone, timeLabel } from './opsFormat';

defineProps<{
  sources: OpsSource[];
}>();
</script>

<template>
  <!-- News sources -->
  <section class="ops-card" data-role="ops-sources">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Ingestion</p>
        <h2 class="ops-card-title">新闻源健康</h2>
      </div>
      <span class="ops-count">{{ sources.length }}</span>
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
            <span class="text-[10px] uppercase tracking-[0.14em] text-[#ffb77d]">{{ source.market }}</span>
            <span
              v-if="source.last_status"
              class="pill ops-status-pill"
              :data-status="source.last_status"
            >{{ source.last_status }}</span>
            <span v-if="source.is_disabled" class="pill ops-pill-crit">disabled</span>
          </div>
          <div class="ops-meta">
            成功率 {{ ratePct(source.success_rate) }} · 连败 {{ source.consecutive_failures }} · 时延 {{ latencyLabel(source.avg_latency_ms) }} · {{ source.source_type }}
          </div>
          <div class="ops-diagnostics" data-role="ops-source-diagnostics">
            <span v-if="source.last_http_status != null">HTTP {{ source.last_http_status }}</span>
            <span>解析 {{ source.last_fetched_count ?? 0 }}</span>
            <span>入库 {{ source.last_inserted_count ?? 0 }}</span>
            <span>空批 {{ source.consecutive_empty_batches ?? 0 }}</span>
          </div>
          <div v-if="source.last_error" class="ops-error-line" data-role="ops-source-error">
            {{ source.last_error }}
          </div>
        </div>
        <div class="ops-row-aside">
          <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
          <span class="text-[11px] text-muted">{{ timeLabel(source.last_success_at) }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.ops-card {
  background: var(--panel);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  border-radius: 18px;
  padding: 16px 16px;
  backdrop-filter: blur(12px);
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
  color: #ffb77d;
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
  background: rgba(255, 255, 255, 0.04);
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
  background: rgba(255, 255, 255, 0.025);
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
  color: #ff8a9c;
  word-break: break-word;
}

.pill.ops-status-pill {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-soft);
}

.pill.ops-status-pill[data-status='ok'],
.pill.ops-status-pill[data-status='not_modified'] {
  background: rgba(57, 200, 132, 0.14);
  color: #5bd49a;
}

.pill.ops-status-pill[data-status='empty'] {
  background: rgba(255, 159, 47, 0.14);
  color: #ffb25c;
}

.pill.ops-status-pill[data-status='parse_error'],
.pill.ops-status-pill[data-status='http_error'] {
  background: rgba(255, 111, 134, 0.14);
  color: #ff8a9c;
}

.ops-mini-dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--muted);
}

.ops-mini-dot--ok { background: #39c884; box-shadow: 0 0 6px rgba(57, 200, 132, 0.5); }
.ops-mini-dot--warning { background: #ff9f2f; box-shadow: 0 0 6px rgba(255, 159, 47, 0.5); }
.ops-mini-dot--critical { background: #ff6f86; box-shadow: 0 0 6px rgba(255, 111, 134, 0.55); }
.ops-mini-dot--neutral { background: #53c2ff; box-shadow: 0 0 6px rgba(83, 194, 255, 0.4); }

/* 复用 pill 结构的严重红变体（main.css 未内置该色 pill） */
.pill.ops-pill-crit {
  background: rgba(255, 111, 134, 0.14);
  color: #ff8a9c;
}
</style>
