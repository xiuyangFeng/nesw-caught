<script setup lang="ts">
import type { OpsWorker } from '../../types/api';
import { ageLabel, timeLabel, workerTone } from './opsFormat';

defineProps<{
  workers: OpsWorker[];
}>();
</script>

<template>
  <!-- Workers -->
  <section class="ops-card" data-role="ops-workers">
    <div class="ops-card-head">
      <div>
        <p class="ops-eyebrow">Runtime</p>
        <h2 class="ops-card-title">后台 Workers</h2>
      </div>
      <span class="ops-count">{{ workers.length }}</span>
    </div>
    <div v-if="workers.length === 0" class="ops-empty">暂无 worker 运行记录</div>
    <div v-else class="grid gap-2">
      <article
        v-for="worker in workers"
        :key="worker.name"
        class="ops-row"
        data-role="ops-worker-row"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="ops-mini-dot" :class="`ops-mini-dot--${workerTone(worker.status)}`" />
            <strong class="truncate text-[13px]">{{ worker.name }}</strong>
            <span class="pill" :class="workerTone(worker.status) === 'ok' ? 'success' : workerTone(worker.status) === 'warning' ? 'ops-pill-warn' : 'neutral'">
              {{ worker.status }}
            </span>
          </div>
          <div class="ops-meta">
            心跳 {{ ageLabel(worker.heartbeat_age_seconds) }} · 成功 {{ worker.success_count }} / 失败 {{ worker.failure_count }} · 周期 {{ worker.cycle_count }}
          </div>
          <div v-if="worker.last_error" class="ops-error-line">最近错误：{{ worker.last_error }}</div>
        </div>
        <div class="ops-row-aside">
          <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
          <span class="text-[11px] text-muted">{{ timeLabel(worker.last_success_at) }}</span>
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

.ops-error-line {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: #ff8a9c;
  word-break: break-word;
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

/* 复用 pill 结构的告警橙变体（main.css 未内置橙色 pill） */
.pill.ops-pill-warn {
  background: rgba(255, 159, 47, 0.14);
  color: #ffb264;
}
</style>
