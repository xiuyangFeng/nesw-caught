<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { apiClient } from '../api/client';
import type { OpsAlert, OpsHealth } from '../types/api';
import { formatMarketTime } from '../utils/time';

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

function timeLabel(iso: string | null | undefined): string {
  if (!iso) {
    return '--';
  }
  return `${formatMarketTime(iso, 'hk')} HKT`;
}

function ageLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return '无心跳';
  }
  if (seconds < 60) {
    return `${Math.round(seconds)}s 前`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m 前`;
  }
  return `${(seconds / 3600).toFixed(1)}h 前`;
}

function ratePct(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return '--';
  }
  return `${(rate * 100).toFixed(1)}%`;
}

function latencyLabel(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) {
    return '--';
  }
  return `${Math.round(ms)}ms`;
}

function numberLabel(value: number): string {
  return value.toLocaleString('en-US');
}

// worker 状态 -> 语义色。degraded 视为告警橙，ok 绿，其余中性。
function workerTone(status: string): 'ok' | 'warning' | 'critical' | 'neutral' {
  if (status === 'ok') {
    return 'ok';
  }
  if (status === 'degraded') {
    return 'warning';
  }
  return 'neutral';
}

function sourceTone(consecutiveFailures: number, disabled: boolean): 'ok' | 'warning' | 'critical' | 'neutral' {
  if (disabled) {
    return 'critical';
  }
  if (consecutiveFailures >= 5) {
    return 'warning';
  }
  if (consecutiveFailures > 0) {
    return 'neutral';
  }
  return 'ok';
}
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

    <!-- 分区网格 -->
    <div class="grid gap-4 xl:grid-cols-2" data-role="ops-sections">
      <!-- Workers -->
      <section class="ops-card" data-role="ops-workers">
        <div class="ops-card-head">
          <div>
            <p class="ops-eyebrow">Runtime</p>
            <h2 class="ops-card-title">后台 Workers</h2>
          </div>
          <span class="ops-count">{{ health?.workers.length ?? 0 }}</span>
        </div>
        <div v-if="!health || health.workers.length === 0" class="ops-empty">暂无 worker 运行记录</div>
        <div v-else class="grid gap-2">
          <article
            v-for="worker in health.workers"
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

      <!-- LLM usage -->
      <section class="ops-card" data-role="ops-llm">
        <div class="ops-card-head">
          <div>
            <p class="ops-eyebrow">Cost</p>
            <h2 class="ops-card-title">LLM 用量 · 近 {{ health?.llm_usage.window_hours ?? 24 }}h</h2>
          </div>
          <span class="ops-count">{{ numberLabel(health?.llm_usage.call_count ?? 0) }} 次</span>
        </div>
        <div class="ops-stat-grid">
          <div class="ops-stat">
            <span class="ops-stat-val">{{ numberLabel(health?.llm_usage.total_tokens ?? 0) }}</span>
            <span class="ops-stat-label">总 tokens</span>
          </div>
          <div class="ops-stat">
            <span class="ops-stat-val">{{ numberLabel(health?.llm_usage.prompt_tokens ?? 0) }}</span>
            <span class="ops-stat-label">prompt</span>
          </div>
          <div class="ops-stat">
            <span class="ops-stat-val">{{ numberLabel(health?.llm_usage.completion_tokens ?? 0) }}</span>
            <span class="ops-stat-label">completion</span>
          </div>
        </div>
        <div v-if="health && health.llm_usage.models.length > 0" class="mt-3 grid gap-1.5">
          <div
            v-for="model in health.llm_usage.models"
            :key="model.model_name"
            class="ops-model-row"
          >
            <span class="truncate text-[12px] text-text-soft">{{ model.model_name }}</span>
            <span class="text-[11px] text-muted">{{ numberLabel(model.total_tokens) }} tok · {{ model.call_count }} 次</span>
          </div>
        </div>
        <div v-else class="ops-empty">近 24h 无 LLM 调用</div>
      </section>

      <!-- News sources -->
      <section class="ops-card" data-role="ops-sources">
        <div class="ops-card-head">
          <div>
            <p class="ops-eyebrow">Ingestion</p>
            <h2 class="ops-card-title">新闻源健康</h2>
          </div>
          <span class="ops-count">{{ health?.sources.length ?? 0 }}</span>
        </div>
        <div v-if="!health || health.sources.length === 0" class="ops-empty">暂无新闻源记录</div>
        <div v-else class="ops-scroller grid gap-2">
          <article
            v-for="source in health.sources"
            :key="`${source.source_name}-${source.market}`"
            class="ops-row"
            data-role="ops-source-row"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="ops-mini-dot" :class="`ops-mini-dot--${sourceTone(source.consecutive_failures, source.is_disabled)}`" />
                <strong class="truncate text-[13px]">{{ source.source_name }}</strong>
                <span class="text-[10px] uppercase tracking-[0.14em] text-[#ffb77d]">{{ source.market }}</span>
                <span v-if="source.is_disabled" class="pill ops-pill-crit">disabled</span>
              </div>
              <div class="ops-meta">
                成功率 {{ ratePct(source.success_rate) }} · 连败 {{ source.consecutive_failures }} · 时延 {{ latencyLabel(source.avg_latency_ms) }} · {{ source.source_type }}
              </div>
            </div>
            <div class="ops-row-aside">
              <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
              <span class="text-[11px] text-muted">{{ timeLabel(source.last_success_at) }}</span>
            </div>
          </article>
        </div>
      </section>

      <!-- X sources + Event bus + Database 合并到右列 -->
      <div class="grid gap-4">
        <section class="ops-card" data-role="ops-x-sources">
          <div class="ops-card-head">
            <div>
              <p class="ops-eyebrow">Social</p>
              <h2 class="ops-card-title">X 数据源</h2>
            </div>
            <span class="ops-count">{{ health?.x_sources.length ?? 0 }}</span>
          </div>
          <div v-if="!health || health.x_sources.length === 0" class="ops-empty">暂无 X 源记录</div>
          <div v-else class="grid gap-2">
            <article
              v-for="x in health.x_sources"
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
                  成功率 {{ ratePct(x.success_rate) }} · 连败 {{ x.consecutive_failures }} · 时延 {{ latencyLabel(x.avg_latency_ms) }}
                </div>
                <div v-if="x.last_error" class="ops-error-line">最近错误：{{ x.last_error }}</div>
              </div>
              <div class="ops-row-aside">
                <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">最近成功</span>
                <span class="text-[11px] text-muted">{{ timeLabel(x.last_success_at) }}</span>
              </div>
            </article>
          </div>
        </section>

        <section class="ops-card" data-role="ops-event-bus">
          <div class="ops-card-head">
            <div>
              <p class="ops-eyebrow">Streaming</p>
              <h2 class="ops-card-title">事件层</h2>
            </div>
            <span
              v-if="health"
              class="pill"
              :class="health.event_bus.status === 'ok' ? 'success' : 'ops-pill-warn'"
            >
              {{ health.event_bus.status }}
            </span>
          </div>
          <div v-if="health" class="grid gap-1.5 text-[12px] text-text-soft">
            <div class="ops-kv"><span>backend</span><span>{{ health.event_bus.backend }}</span></div>
            <div class="ops-kv"><span>redis</span><span>{{ health.event_bus.redis_enabled ? '已启用' : '未启用' }}</span></div>
            <div class="ops-kv"><span>最近事件</span><span>{{ health.event_bus.last_event_name ?? '--' }}</span></div>
            <div class="ops-kv"><span>最近发布</span><span>{{ timeLabel(health.event_bus.last_published_at) }}</span></div>
            <div v-if="health.event_bus.last_error" class="ops-error-line">错误：{{ health.event_bus.last_error }}</div>
          </div>
          <div v-else class="ops-empty">加载中…</div>
        </section>

        <section class="ops-card" data-role="ops-database">
          <div class="ops-card-head">
            <div>
              <p class="ops-eyebrow">Storage</p>
              <h2 class="ops-card-title">数据库体积</h2>
            </div>
            <span v-if="health" class="ops-count">{{ health.database.size_mb.toFixed(2) }} MB</span>
          </div>
          <div v-if="health" class="grid gap-1.5 text-[12px] text-text-soft">
            <div class="ops-kv"><span>字节</span><span>{{ numberLabel(health.database.size_bytes) }}</span></div>
            <div class="ops-kv"><span>存在</span><span>{{ health.database.exists ? '是' : '否' }}</span></div>
            <div v-if="health.database.path" class="ops-db-path">{{ health.database.path }}</div>
          </div>
          <div v-else class="ops-empty">加载中…</div>
        </section>
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

/* --- 分区卡片 --- */
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

.ops-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.ops-stat {
  display: grid;
  gap: 2px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.025);
  padding: 10px 12px;
}

.ops-stat-val {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.ops-stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-faint);
}

.ops-model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
  padding: 8px 10px;
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
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  color: var(--muted);
  word-break: break-all;
}

/* 复用 pill 结构的告警橙 / 严重红变体（main.css 未内置橙色 pill） */
.pill.ops-pill-warn {
  background: rgba(255, 159, 47, 0.14);
  color: #ffb264;
}

.pill.ops-pill-crit {
  background: rgba(255, 111, 134, 0.14);
  color: #ff8a9c;
}
</style>
