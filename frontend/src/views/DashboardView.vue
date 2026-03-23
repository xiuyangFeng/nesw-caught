<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import HeroMetrics from '../components/dashboard/HeroMetrics.vue';
import TopicBoard from '../components/dashboard/TopicBoard.vue';
import { useConnectionStore } from '../stores/connectionStore';
import { useMarketStore } from '../stores/marketStore';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import type { Market } from '../types/api';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const topicStore = useTopicStore();
const router = useRouter();

const moverPreviewItems = computed(() => marketStore.abnormalMovers.slice(0, 2));
const dashboardFeedItems = computed(() => newsStore.dashboardItems.slice(0, 8));

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

const moverMarketSummary = computed(() => {
  const counts: Record<Market, number> = { hk: 0, us: 0, cn: 0 };

  for (const item of marketStore.abnormalMovers) {
    counts[item.market] += 1;
  }

  return (Object.entries(counts) as Array<[Market, number]>)
    .filter(([, count]) => count > 0)
    .map(([market, count]) => `${marketLabelMap[market]} ${count}`)
    .join(' / ');
});

const topMoverReason = computed(() => {
  const reasonCounts = new Map<string, number>();

  for (const item of marketStore.abnormalMovers) {
    const reason = item.abnormal_reason ?? 'unknown';
    reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
  }

  const [topReason] =
    [...reasonCounts.entries()].sort((left, right) => right[1] - left[1])[0] ?? [];

  return abnormalReasonLabelMap[topReason ?? ''] ?? '异动信号';
});

function getAbnormalReasonLabel(reason: string | null) {
  if (!reason) {
    return '异动信号';
  }
  return abnormalReasonLabelMap[reason] ?? reason;
}

function getDashboardNewsTimestampLabel(timestamp: string, market: Market) {
  return `${formatMarketTime(timestamp, market)} ${getMarketTimezoneLabel(market)}`;
}

function openDashboardStory(id: number) {
  router.push({ name: 'news-detail', params: { id } });
}

const dashboardStatus = computed(() => {
  if (connectionStore.state === 'live') {
    return {
      label: '在线',
      detail: 'SSE live',
      tone: 'success',
    } as const;
  }
  if (connectionStore.state === 'degraded') {
    return {
      label: '降级',
      detail: connectionStore.usingMock ? 'mock' : 'degraded',
      tone: 'warning',
    } as const;
  }
  if (connectionStore.state === 'offline') {
    return {
      label: '离线',
      detail: 'SSE off',
      tone: 'danger',
    } as const;
  }
  return {
    label: '连接中',
    detail: 'SSE wait',
    tone: 'default',
  } as const;
});

const metrics = computed(() => {
  const positive = newsStore.dashboardItems.filter((item) => item.sentiment_label === 'positive').length;
  const negative = newsStore.dashboardItems.filter((item) => item.sentiment_label === 'negative').length;
  return [
    {
      label: '新闻总量',
      value: String(newsStore.dashboardItems.length),
      note: '当前已加载新闻',
      tone: 'default' as const,
    },
    {
      label: '偏利好',
      value: String(positive),
      note: '情绪标签入口',
      tone: 'positive' as const,
      to: '/news/sentiment/positive',
    },
    {
      label: '偏利空',
      value: String(negative),
      note: '风险侧新闻入口',
      tone: 'negative' as const,
      to: '/news/sentiment/negative',
    },
    {
      label: '异动股票',
      value: String(marketStore.abnormalMovers.length),
      note: '自选股异动入口',
      tone: marketStore.abnormalMovers.length ? 'negative' : 'default',
      to: '/watchlist',
    },
  ];
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Control Room</p>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">
          Market Control：把连接状态、情绪概览、主题聚合和自选股异动压缩到同一块总览面板里。
        </p>
      </div>
      <div class="flex items-center gap-2 self-start">
        <span
          class="dashboard-status-badge"
          :class="`dashboard-status-badge--${dashboardStatus.tone}`"
          data-role="dashboard-status-badge"
        >
          <span class="dashboard-status-badge__dot" />
          <span>{{ dashboardStatus.label }}</span>
          <small>{{ dashboardStatus.detail }}</small>
        </span>
        <StaleBadge :stale="newsStore.dashboardStale || marketStore.stale || topicStore.stale" label="全局数据" />
      </div>
    </header>

    <div data-role="dashboard-hero">
      <p class="mb-2.5 text-[11px] uppercase tracking-[0.18em] text-system">Signal Overview</p>
      <HeroMetrics :metrics="metrics" />
    </div>

    <section class="grid gap-[14px] xl:grid-cols-[1.35fr_1fr_0.72fr]" data-role="dashboard-columns">
      <SectionCard
        class="h-full"
        eyebrow="News Wire"
        title="News Feed"
        subtitle="新闻主列，保持紧凑扫描密度"
        data-role="dashboard-column-feed"
      >
        <LoadingBlock :loading="newsStore.dashboardLoading" :empty="newsStore.dashboardItems.length === 0">
          <div class="grid gap-3">
            <div class="dashboard-column-scroller" data-role="dashboard-column-scroller">
              <button
                v-for="item in dashboardFeedItems"
                :key="item.id"
                class="dashboard-feed-item"
                data-role="dashboard-feed-item"
                type="button"
                @click="openDashboardStory(item.id)"
              >
                <div class="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                  <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                  <span>{{ item.source_name }}</span>
                  <span>{{ getDashboardNewsTimestampLabel(getNewsDisplayTimestamp(item), item.market) }}</span>
                </div>
                <strong class="block text-[14px] leading-5 text-text">{{ item.title }}</strong>
                <p class="m-0 line-clamp-1 text-[12px] leading-5 text-muted">{{ item.summary }}</p>
              </button>
            </div>

            <RouterLink
              class="inline-flex min-h-10 items-center justify-center rounded-full border border-border bg-white/[0.04] text-[13px] font-semibold text-text transition duration-150 ease-out hover:-translate-y-px hover:border-system/25 hover:bg-white/[0.06]"
              to="/news"
            >
              打开完整 News Feed
            </RouterLink>
          </div>
        </LoadingBlock>
      </SectionCard>

      <SectionCard
        class="h-full"
        eyebrow="Topic Radar"
        title="主题聚合"
        subtitle="按重要度排序，保留股票和情绪入口"
        data-role="dashboard-column-topics"
      >
        <LoadingBlock :loading="topicStore.loading" :empty="topicStore.topTopics.length === 0">
          <div class="dashboard-column-scroller dashboard-topic-column" data-role="dashboard-column-scroller">
            <TopicBoard :topics="topicStore.topTopics" />
          </div>
        </LoadingBlock>
      </SectionCard>

      <SectionCard
        class="h-full dashboard-column--movers"
        eyebrow="Live Movers"
        title="自选股异动"
        subtitle="盘中优先观察异常波动和量能变化"
        data-role="dashboard-column-movers"
      >
        <LoadingBlock :loading="marketStore.loading" :empty="marketStore.abnormalMovers.length === 0" empty-text="暂无异动">
          <div class="grid gap-3">
            <section
              class="grid gap-1.5 rounded-[16px] border border-[#ff9f2f33] bg-[linear-gradient(160deg,rgba(19,26,37,0.96),rgba(8,16,26,0.98))] px-3.5 py-3"
              data-role="movement-summary"
            >
              <div class="flex items-end justify-between gap-3">
                <div>
                  <p class="mb-1 text-[10px] uppercase tracking-[0.16em] text-system">Signal Count</p>
                  <strong class="block text-[24px] leading-none">{{ marketStore.abnormalMovers.length }} 只异动</strong>
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
                    <span class="text-[10px] uppercase tracking-[0.14em] text-[#ffb77d]">{{ marketLabelMap[item.market] }}</span>
                  </div>
                  <span class="block truncate text-[11px] text-muted">{{ item.symbol }}</span>
                </div>
                <em class="dashboard-inline-meta whitespace-nowrap not-italic">{{ getAbnormalReasonLabel(item.abnormal_reason) }}</em>
              </article>
              </div>
            </div>

            <RouterLink
              class="inline-flex min-h-10 items-center justify-center rounded-full border border-[#3aa9f557] bg-[rgba(10,26,42,0.72)] text-[13px] font-semibold text-[#9bd8ff] transition duration-150 ease-out hover:-translate-y-px hover:border-[#3aa9f59e] hover:bg-[rgba(15,39,61,0.92)]"
              to="/watchlist"
            >
              查看全部异动
            </RouterLink>
          </div>
        </LoadingBlock>
      </SectionCard>
    </section>
  </div>
</template>

<style scoped>
.dashboard-column-scroller {
  display: grid;
  gap: 10px;
}

.dashboard-compact-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
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

.dashboard-feed-item {
  display: grid;
  gap: 6px;
  width: 100%;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.025);
  padding: 12px 12px;
  text-align: left;
  cursor: pointer;
  transition: transform 150ms ease, border-color 150ms ease, background 150ms ease;
}

.dashboard-feed-item:hover {
  transform: translateY(-1px);
  border-color: rgba(58, 169, 245, 0.35);
  background: rgba(255, 255, 255, 0.05);
}

.dashboard-feed-item:focus-visible {
  outline: 2px solid rgba(58, 169, 245, 0.72);
  outline-offset: 2px;
}

.dashboard-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.035);
  padding: 7px 10px;
  font-size: 11px;
  line-height: 1;
  color: var(--muted);
}

.dashboard-status-badge small {
  color: var(--text-faint);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.dashboard-status-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.04);
}

.dashboard-status-badge--success {
  color: #7ed89e;
}

.dashboard-status-badge--warning {
  color: #efc16e;
}

.dashboard-status-badge--danger {
  color: #ef7b7b;
}

.dashboard-status-badge--default {
  color: #92a5bb;
}

@media (min-width: 1280px) {
  .dashboard-column-scroller {
    max-height: clamp(28rem, calc(100vh - 21rem), 40rem);
    overflow-y: auto;
    padding-right: 4px;
  }
}

.dashboard-topic-column :deep(.terminal-surface) {
  border-radius: 16px;
  padding: 12px;
}

.dashboard-topic-column :deep(.terminal-surface strong.text-base) {
  font-size: 14px;
  line-height: 1.35;
}

.dashboard-topic-column :deep(.terminal-surface p.my-3) {
  margin: 8px 0;
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.dashboard-topic-column :deep([data-role='topic-meta']) {
  gap: 8px;
  font-size: 11px;
  line-height: 1.45;
}
</style>
