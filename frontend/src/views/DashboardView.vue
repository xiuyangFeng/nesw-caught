<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import HeroMetrics from '../components/dashboard/HeroMetrics.vue';
import SourceHealthGrid from '../components/dashboard/SourceHealthGrid.vue';
import TopicBoard from '../components/dashboard/TopicBoard.vue';
import SentimentGauge from '../components/dashboard/SentimentGauge.vue';
import SentimentTrendChart from '../components/dashboard/SentimentTrendChart.vue';
import BreakingNewsSpotlight from '../components/dashboard/BreakingNewsSpotlight.vue';
import NewsDetailDrawer from '../components/news/NewsDetailDrawer.vue';
import { useConnectionStore } from '../stores/connectionStore';
import { useMarketStore } from '../stores/marketStore';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import type { Market } from '../types/api';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp, isMarket, normalizeMarket } from '../utils/time';

const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const topicStore = useTopicStore();
const router = useRouter();

// 交互式过滤器状态
const selectedMarket = ref<Market | null>(null);
const selectedSentiment = ref<string | null>(null);

// 新闻预览抽屉状态
const drawerVisible = ref(false);
const selectedNewsId = ref<number | null>(null);

const markets = [
  { label: '全部', value: null },
  { label: 'A股', value: 'cn' as const },
  { label: '港股', value: 'hk' as const },
  { label: '美股', value: 'us' as const },
];

const sentiments = [
  { label: '全部', value: null },
  { label: '偏利好', value: 'positive' },
  { label: '偏利空', value: 'negative' },
];

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

// 1. 过滤新闻流
const filteredDashboardItems = computed(() => {
  return newsStore.dashboardItems.filter((item) => {
    if (selectedMarket.value && item.market !== selectedMarket.value) {
      return false;
    }
    if (selectedSentiment.value && item.sentiment_label !== selectedSentiment.value) {
      return false;
    }
    return true;
  });
});

// 2. 抽屉所用的 ID 映射
const filteredNewsIds = computed(() => {
  return filteredDashboardItems.value.map((item) => item.id);
});

// 3. 过滤自选股异动
const filteredMovers = computed(() => {
  if (!selectedMarket.value) {
    return marketStore.abnormalMovers;
  }
  return marketStore.abnormalMovers.filter((item) => item.market === selectedMarket.value);
});

const moverPreviewItems = computed(() => filteredMovers.value.slice(0, 2));
const dashboardFeedItems = computed(() => filteredDashboardItems.value.slice(0, 8));

// 4. 过滤主题
const filteredTopics = computed(() => {
  if (!selectedMarket.value) {
    return topicStore.topTopics;
  }
  return topicStore.topTopics.filter((item) => item.market === selectedMarket.value);
});

const moverMarketSummary = computed(() => {
  const counts: Record<Market, number> = { hk: 0, us: 0, cn: 0 };

  for (const item of filteredMovers.value) {
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

  for (const item of filteredMovers.value) {
    const reason = item.abnormal_reason ?? 'unknown';
    reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
  }

  const [topReason] =
    [...reasonCounts.entries()].sort((left, right) => right[1] - left[1])[0] ?? [];

  return abnormalReasonLabelMap[topReason ?? ''] ?? '异动信号';
});

function getAbnormalReasonLabel(reason: string | null | undefined) {
  if (!reason) {
    return '异动信号';
  }
  return abnormalReasonLabelMap[reason] ?? reason;
}

function getDashboardNewsTimestampLabel(timestamp: string | null, market: string) {
  return `${formatMarketTime(timestamp, market)} ${getMarketTimezoneLabel(market)}`;
}

// 抽屉交互函数
function openNewsDrawer(id: number) {
  selectedNewsId.value = id;
  drawerVisible.value = true;
}

// 24小时情绪走势计算数据
const positive24hTrend = computed(() =>
  hourlyTrend((item) => item.sentiment_label === 'positive', 24)
);
const negative24hTrend = computed(() =>
  hourlyTrend((item) => item.sentiment_label === 'negative', 24)
);

function closeNewsDrawer() {
  drawerVisible.value = false;
  selectedNewsId.value = null;
}

function changeNewsInDrawer(id: number) {
  selectedNewsId.value = id;
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

function hourlyTrend(
  predicate?: (item: (typeof newsStore.dashboardItems)[number]) => boolean,
  hours = 12
) {
  const buckets = new Array<number>(hours).fill(0);
  const now = Date.now();
  // 使用过滤后的新闻列表重新绘折线图
  for (const item of filteredDashboardItems.value) {
    if (predicate && !predicate(item)) {
      continue;
    }
    const rawTimestamp = getNewsDisplayTimestamp(item);
    if (!rawTimestamp) {
      continue;
    }
    const timestamp = new Date(rawTimestamp).getTime();
    if (Number.isNaN(timestamp)) {
      continue;
    }
    const bucketIndex = Math.floor((now - timestamp) / 3_600_000);
    if (bucketIndex >= 0 && bucketIndex < hours) {
      buckets[hours - 1 - bucketIndex] += 1;
    }
  }
  return buckets;
}

const sourceHealthItems = computed(() => newsStore.newsRuntimeStatus?.sources ?? []);

const positiveCount = computed(() => {
  return filteredDashboardItems.value.filter((item) => item.sentiment_label === 'positive').length;
});

const negativeCount = computed(() => {
  return filteredDashboardItems.value.filter((item) => item.sentiment_label === 'negative').length;
});

const metrics = computed(() => {
  const totalCount = filteredDashboardItems.value.length;
  const positive = positiveCount.value;
  const negative = negativeCount.value;
  const moverCount = filteredMovers.value.length;
  return [
    {
      label: '新闻总量',
      value: String(totalCount),
      note: '当前过滤新闻数',
      tone: 'default' as const,
      trend: hourlyTrend(),
    },
    {
      label: '偏利好',
      value: String(positive),
      note: '利好情感量',
      tone: 'positive' as const,
      to: '/news/sentiment/positive',
      trend: hourlyTrend((item) => item.sentiment_label === 'positive'),
    },
    {
      label: '偏利空',
      value: String(negative),
      note: '风险侧消息量',
      tone: 'negative' as const,
      to: '/news/sentiment/negative',
      trend: hourlyTrend((item) => item.sentiment_label === 'negative'),
    },
    {
      label: '异动股票',
      value: String(moverCount),
      note: '自选股波动计数',
      tone: moverCount ? ('negative' as const) : ('default' as const),
      to: '/watchlist',
    },
  ];
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Secondary Overview</p>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">
          Overview Snapshot：为最新事件页提供连接状态、主题舆情和自选股异动的多维交互控制台。
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

    <!-- 顶部突发利好/利空警报横幅 -->
    <BreakingNewsSpotlight :newsItems="filteredDashboardItems" @selectNews="openNewsDrawer" />

    <!-- 舆情偏好罗盘与指标网格 -->
    <div data-role="dashboard-hero" class="grid gap-3.5 xl:grid-cols-[1.1fr_1.8fr_2.1fr]">
      <SentimentGauge :positiveCount="positiveCount" :negativeCount="negativeCount" />
      
      <SentimentTrendChart :positiveTrend="positive24hTrend" :negativeTrend="negative24hTrend" />
      
      <div class="flex flex-col justify-between gap-3.5">
        <div class="surface rounded-[14px] border border-border/80 bg-panel-soft/60 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div class="flex items-center gap-1.5">
            <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">市场范围</span>
            <button
              v-for="m in markets"
              :key="m.value ?? 'all'"
              class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
              :class="selectedMarket === m.value ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
              type="button"
              @click="selectedMarket = m.value"
            >
              {{ m.label }}
            </button>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">舆情过滤</span>
            <button
              v-for="s in sentiments"
              :key="s.value ?? 'all'"
              class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
              :class="selectedSentiment === s.value ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
              type="button"
              @click="selectedSentiment = s.value"
            >
              {{ s.label }}
            </button>
          </div>
        </div>

        <HeroMetrics :metrics="metrics" class="flex-grow" />
      </div>
    </div>

    <section class="grid gap-[14px] xl:grid-cols-[1.35fr_1fr_0.72fr]" data-role="dashboard-columns">
      <SectionCard
        class="h-full"
        eyebrow="News Wire"
        title="News Feed"
        subtitle="新闻主列，保持紧凑扫描密度"
        data-role="dashboard-column-feed"
      >
        <LoadingBlock :loading="newsStore.dashboardLoading" :empty="filteredDashboardItems.length === 0" :skeletonType="'news'" :skeletonCount="3">
          <div class="grid gap-3">
            <div class="dashboard-column-scroller" data-role="dashboard-column-scroller">
              <button
                v-for="item in dashboardFeedItems"
                :key="item.id"
                class="dashboard-feed-item"
                :class="{
                  'dashboard-feed-item--breaking': (item as any).editorial_score >= 8.5,
                  'positive': item.sentiment_label === 'positive',
                  'negative': item.sentiment_label === 'negative'
                }"
                data-role="dashboard-feed-item"
                type="button"
                @click="openNewsDrawer(item.id)"
              >
                <div class="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                  <span
                    v-if="(item as any).editorial_score >= 8.5"
                    class="inline-flex h-2 w-2 rounded-full shrink-0 animate-pulse"
                    :class="item.sentiment_label === 'positive' ? 'bg-positive' : 'bg-negative'"
                  />
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
        <LoadingBlock :loading="topicStore.loading" :empty="filteredTopics.length === 0" :skeletonType="'watchlist'" :skeletonCount="2">
          <div class="dashboard-column-scroller dashboard-topic-column" data-role="dashboard-column-scroller">
            <TopicBoard :topics="filteredTopics" />
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
        <LoadingBlock :loading="marketStore.loading" :empty="filteredMovers.length === 0" :skeletonType="'watchlist'" :skeletonCount="2" empty-text="暂无异动">
          <div class="grid gap-3">
            <section
              class="grid gap-1.5 rounded-[16px] border border-[#ff9f2f33] bg-[linear-gradient(160deg,rgba(19,26,37,0.96),rgba(8,16,26,0.98))] px-3.5 py-3"
              data-role="movement-summary"
            >
              <div class="flex items-end justify-between gap-3">
                <div>
                  <p class="mb-1 text-[10px] uppercase tracking-[0.16em] text-system">Signal Count</p>
                  <strong class="block text-[24px] leading-none">{{ filteredMovers.length }} 只异动</strong>
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
                    <span class="text-[10px] uppercase tracking-[0.14em] text-[#ffb77d]">{{ marketLabelMap[normalizeMarket(item.market)] }}</span>
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

    <SectionCard
      eyebrow="Source Health"
      title="来源健康"
      subtitle="按状态排序:故障源置顶,EMA 时延与连续失败可见"
      data-role="dashboard-source-health"
    >
      <SourceHealthGrid :sources="sourceHealthItems" />
    </SectionCard>

    <!-- 极速右侧滑出预览抽屉 -->
    <NewsDetailDrawer
      :newsId="selectedNewsId"
      :visible="drawerVisible"
      :filteredNewsIds="filteredNewsIds"
      @close="closeNewsDrawer"
      @changeNews="changeNewsInDrawer"
    />
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

.dashboard-feed-item--breaking {
  position: relative;
  border-left-width: 4px;
  border-left-style: solid;
  border-left-color: var(--accent);
}

.dashboard-feed-item--breaking.positive {
  border-left-color: var(--positive);
  box-shadow: 0 0 16px rgba(255, 111, 134, 0.08);
  background: linear-gradient(90deg, rgba(255, 111, 134, 0.04) 0%, rgba(255, 111, 134, 0.01) 30%, rgba(255, 255, 255, 0.025) 100%);
}

.dashboard-feed-item--breaking.negative {
  border-left-color: var(--negative);
  box-shadow: 0 0 16px rgba(57, 200, 132, 0.08);
  background: linear-gradient(90deg, rgba(57, 200, 132, 0.04) 0%, rgba(57, 200, 132, 0.01) 30%, rgba(255, 255, 255, 0.025) 100%);
}

.dashboard-feed-item--breaking:hover {
  transform: translateY(-1px);
}

.dashboard-feed-item--breaking.positive:hover {
  border-color: var(--positive);
  box-shadow: 0 0 20px rgba(255, 111, 134, 0.16);
  background: linear-gradient(90deg, rgba(255, 111, 134, 0.06) 0%, rgba(255, 111, 134, 0.02) 40%, rgba(255, 255, 255, 0.05) 100%);
}

.dashboard-feed-item--breaking.negative:hover {
  border-color: var(--negative);
  box-shadow: 0 0 20px rgba(57, 200, 132, 0.16);
  background: linear-gradient(90deg, rgba(57, 200, 132, 0.06) 0%, rgba(57, 200, 132, 0.02) 40%, rgba(255, 255, 255, 0.05) 100%);
}
</style>
