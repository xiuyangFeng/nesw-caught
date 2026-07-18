<script setup lang="ts">
import type { OpsDatabase, OpsEventBus } from '../../types/api';
import { numberLabel, timeLabel } from './opsFormat';

defineProps<{
  eventBus: OpsEventBus | null;
  database: OpsDatabase | null;
}>();
</script>

<template>
  <section class="surface ops-card" data-role="ops-event-bus">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Streaming</p>
        <h2 class="ops-card-title">事件层</h2>
      </div>
      <span
        v-if="eventBus"
        class="pill"
        :class="eventBus.status === 'ok' ? 'success' : 'warning ops-pill-warn'"
      >
        {{ eventBus.status }}
      </span>
    </div>
    <div v-if="eventBus" class="grid gap-1.5 text-[12px] text-text-soft">
      <div class="ops-kv"><span>backend</span><span>{{ eventBus.backend }}</span></div>
      <div class="ops-kv"><span>redis</span><span>{{ eventBus.redis_enabled ? '已启用' : '未启用' }}</span></div>
      <div class="ops-kv"><span>最近事件</span><span>{{ eventBus.last_event_name ?? '--' }}</span></div>
      <div class="ops-kv"><span>最近发布</span><span class="num">{{ timeLabel(eventBus.last_published_at) }}</span></div>
      <div v-if="eventBus.last_error" class="ops-error-line">错误：{{ eventBus.last_error }}</div>
    </div>
    <div v-else class="ops-empty">加载中…</div>
  </section>

  <section class="surface ops-card" data-role="ops-database">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Storage</p>
        <h2 class="ops-card-title">数据库体积</h2>
      </div>
      <span v-if="database" class="num ops-count">{{ database.size_mb.toFixed(2) }} MB</span>
    </div>
    <div v-if="database" class="grid gap-1.5 text-[12px] text-text-soft">
      <div class="ops-kv"><span>字节</span><span class="num">{{ numberLabel(database.size_bytes) }}</span></div>
      <div class="ops-kv"><span>存在</span><span>{{ database.exists ? '是' : '否' }}</span></div>
      <div v-if="database.path" class="ops-db-path">{{ database.path }}</div>
    </div>
    <div v-else class="ops-empty">加载中…</div>
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

.ops-error-line {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--danger);
  word-break: break-word;
}

.ops-kv {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ops-kv > span:first-child {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-faint);
}

.ops-db-path {
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  word-break: break-all;
}
</style>
