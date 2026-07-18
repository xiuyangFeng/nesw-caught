<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import LoadingBlock from '../common/LoadingBlock.vue';
import SectionCard from '../common/SectionCard.vue';
import type { Market, MarketSnapshot } from '../../types/api';
import { isMarket, normalizeMarket } from '../../utils/time';

const props = defineProps<{
  movers: MarketSnapshot[];
  loading: boolean;
}>();

const marketLabelMap: Record<Market, string> = {
  hk: '港股',
  us: '美股',
  cn: 'A股',
};

const abnormalReasonLabelMap: Record<string, string> = {
  price_move: '价格异动',
  price_spike: '价格急拉',
  volume_spike: '量能放大',
};

function getAbnormalReasonLabel(reason: string | null | undefined) {
  if (!reason) {
    return '异动信号';
  }
  return abnormalReasonLabelMap[reason] ?? reason;
}

const moverPreviewItems = computed(() => props.movers.slice(0, 2));

const moverMarketSummary = computed(() => {
  const counts: Record<Market, number> = { hk: 0, us: 0, cn: 0 };

  for (const item of props.movers) {
    // 后端 market 字段为普通 string,仅统计已知市场
    if (isMarket(item.market)) {
      counts[item.market] += 1;
    }
  }

  return (Object.entries(counts) as Array<[Market, number]>)
    .filter(([, count]) => count > 0)
    .map(([market, count]) => `${marketLabelMap[market]} ${count}`)
    .join(' / ');
});

const topMoverReason = computed(() => {
  const reasonCounts = new Map<string, number>();

  for (const item of props.movers) {
    const reason = item.abnormal_reason ?? 'unknown';
    reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
  }

  const [topReason] =
    [...reasonCounts.entries()].sort((left, right) => right[1] - left[1])[0] ?? [];

  return abnormalReasonLabelMap[topReason ?? ''] ?? '异动信号';
});
</script>

<template>
  <SectionCard
    class="h-full dashboard-column--movers"
    eyebrow="Live Movers"
    title="自选股异动"
    subtitle="盘中优先观察异常波动和量能变化"
    data-role="dashboard-column-movers"
  >
    <LoadingBlock :loading="loading" :empty="movers.length === 0" :skeletonType="'watchlist'" :skeletonCount="2" empty-text="暂无异动">
      <div class="grid gap-3">
        <section
          class="grid gap-1.5 rounded-lg border border-border bg-panel-soft px-3.5 py-3"
          data-role="movement-summary"
        >
          <div class="flex items-end justify-between gap-3">
            <div>
              <p class="mb-1 text-[10px] uppercase tracking-[0.16em] text-muted font-mono">Signal Count</p>
              <strong class="block text-[24px] leading-none font-mono tabular-nums">{{ movers.length }} 只异动</strong>
            </div>
            <span class="rounded-full border border-border bg-white/[0.05] px-2.5 py-1 text-[11px] text-muted">
              主因 {{ topMoverReason }}
            </span>
          </div>
          <p class="m-0 text-[12px] leading-5 text-muted">{{ moverMarketSummary || '暂无市场分布' }}</p>
        </section>

        <div class="dashboard-column-scroller" data-role="dashboard-column-scroller">
          <div class="grid gap-2" data-role="movement-signal-board">
          <article
            v-for="item in moverPreviewItems"
            :key="item.symbol"
            class="dashboard-compact-row dashboard-compact-row--movers"
            data-role="movement-preview-item"
            data-kind="movement-signal-row"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <strong class="block truncate text-[13px]">{{ item.display_name ?? item.symbol }}</strong>
                <span class="text-[10px] uppercase tracking-[0.14em] text-text-faint font-mono">{{ marketLabelMap[normalizeMarket(item.market)] }}</span>
              </div>
              <span class="block truncate text-[11px] text-muted">{{ item.symbol }}</span>
            </div>
            <em class="dashboard-inline-meta whitespace-nowrap not-italic">{{ getAbnormalReasonLabel(item.abnormal_reason) }}</em>
          </article>
          </div>
        </div>

        <RouterLink
          class="inline-flex min-h-10 items-center justify-center rounded-full border border-border bg-white/[0.04] text-[13px] font-semibold text-text transition duration-150 ease-out hover:-translate-y-px hover:border-system/25 hover:bg-white/[0.06]"
          to="/watchlist"
        >
          查看全部异动
        </RouterLink>
      </div>
    </LoadingBlock>
  </SectionCard>
</template>

<style scoped>
.dashboard-column-scroller {
  display: grid;
  gap: 10px;
}

@media (min-width: 1280px) {
  .dashboard-column-scroller {
    max-height: clamp(28rem, calc(100vh - 21rem), 40rem);
    overflow-y: auto;
    padding-right: 4px;
  }
}

.dashboard-compact-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--panel-soft);
  padding: 12px 12px;
}

.dashboard-inline-meta {
  color: var(--system);
  font-size: 11px;
  line-height: 1.4;
}

.dashboard-column--movers :deep(header) p:last-of-type {
  max-width: 18ch;
}

.dashboard-compact-row--movers {
  align-items: flex-start;
  padding: 10px 10px;
}

.dashboard-compact-row--movers .dashboard-inline-meta {
  max-width: 6em;
  text-align: right;
}
</style>
