<script setup lang="ts">
import { computed } from 'vue';

import type { Market, NewsRuntimeSource } from '../../types/api';
import { formatMarketTime } from '../../utils/time';

const props = defineProps<{
  sources: NewsRuntimeSource[];
}>();

const MARKET_LABELS: Record<Market, string> = {
  hk: '港股',
  us: '美股',
  cn: 'A股',
};

const STATUS_META: Record<
  NewsRuntimeSource['status'],
  { label: string; dotClass: string; textClass: string; rank: number }
> = {
  offline: { label: 'OFFLINE', dotClass: 'bg-danger', textClass: 'text-danger', rank: 0 },
  degraded: { label: 'DEGRADED', dotClass: 'bg-warning', textClass: 'text-warning', rank: 1 },
  delayed: { label: 'DELAYED', dotClass: 'bg-warning', textClass: 'text-warning', rank: 2 },
  ok: { label: 'OK', dotClass: 'bg-success', textClass: 'text-success', rank: 3 },
};

// 故障源排前,健康源排后;同状态按名称稳定排序
const sortedSources = computed(() =>
  [...props.sources].sort((left, right) => {
    const rankDelta = STATUS_META[left.status].rank - STATUS_META[right.status].rank;
    if (rankDelta !== 0) {
      return rankDelta;
    }
    return left.source_name.localeCompare(right.source_name);
  }),
);

const healthSummary = computed(() => {
  const counts = { ok: 0, delayed: 0, degraded: 0, offline: 0 };
  for (const source of props.sources) {
    counts[source.status] += 1;
  }
  return counts;
});

function formatLatency(latency: number | null) {
  if (latency === null) {
    return '--';
  }
  return `${Math.round(latency)}ms`;
}

function formatLastSuccess(source: NewsRuntimeSource) {
  if (!source.last_success_at) {
    return '从未成功';
  }
  return `${formatMarketTime(source.last_success_at, source.market)} ${MARKET_LABELS[source.market]}`;
}
</script>

<template>
  <section class="grid gap-3" data-role="source-health-grid">
    <div class="flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.14em]" data-role="source-health-summary">
      <span class="text-success">OK {{ healthSummary.ok }}</span>
      <span class="text-warning">DELAYED {{ healthSummary.delayed + healthSummary.degraded }}</span>
      <span class="text-danger">OFFLINE {{ healthSummary.offline }}</span>
    </div>

    <div class="grid gap-1.5">
      <article
        v-for="source in sortedSources"
        :key="`${source.source_name}-${source.market}`"
        class="source-health-row"
        data-role="source-health-row"
        :data-status="source.status"
      >
        <span class="source-health-row__dot" :class="STATUS_META[source.status].dotClass" />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <strong class="truncate text-[12px] text-text">{{ source.source_name }}</strong>
            <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">{{ MARKET_LABELS[source.market] }}</span>
            <span class="text-[10px] uppercase tracking-[0.12em] text-text-faint">{{ source.tier }}</span>
          </div>
          <span class="block truncate text-[11px] text-muted">
            最近成功 {{ formatLastSuccess(source) }}
            <template v-if="source.consecutive_failures > 0"> · 连续失败 {{ source.consecutive_failures }}</template>
          </span>
        </div>
        <div class="text-right">
          <span class="block font-mono text-[11px]" :class="STATUS_META[source.status].textClass">
            {{ STATUS_META[source.status].label }}
          </span>
          <span class="block font-mono text-[11px] text-text-faint">{{ formatLatency(source.avg_fetch_latency_ms) }}</span>
        </div>
      </article>
    </div>

    <p v-if="sortedSources.length === 0" class="m-0 text-[12px] text-muted">暂无来源健康数据</p>
  </section>
</template>

<style scoped>
.source-health-row {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.025);
  padding: 8px 12px;
}

.source-health-row[data-status='offline'] {
  border-color: var(--danger-soft);
  background: rgba(255, 111, 134, 0.05);
}

.source-health-row__dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.04);
}
</style>
