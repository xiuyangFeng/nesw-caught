<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import HeroMetrics from '../components/dashboard/HeroMetrics.vue';
import TopicBoard from '../components/dashboard/TopicBoard.vue';
import { useConnectionStore } from '../stores/connectionStore';
import { useMarketStore } from '../stores/marketStore';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import type { Market } from '../types/api';

const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const topicStore = useTopicStore();

const moverPreviewItems = computed(() => marketStore.abnormalMovers.slice(0, 3));

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

const metrics = computed(() => {
  const positive = newsStore.items.filter((item) => item.sentiment_label === 'positive').length;
  const negative = newsStore.items.filter((item) => item.sentiment_label === 'negative').length;
  return [
    {
      label: '新闻总量',
      value: String(newsStore.items.length),
      note: '当前已加载新闻',
      tone: 'default' as const,
    },
    {
      label: '偏利好',
      value: String(positive),
      note: '情绪标签入口',
      tone: 'positive' as const,
    },
    {
      label: '偏利空',
      value: String(negative),
      note: '风险侧新闻入口',
      tone: 'negative' as const,
    },
    {
      label: '异动股票',
      value: String(marketStore.abnormalMovers.length),
      note: '自选股异动入口',
      tone: marketStore.abnormalMovers.length ? 'negative' : 'default',
    },
  ];
});
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">
          Market Control：把连接状态、情绪概览、主题聚合和自选股异动压缩到同一块总览面板里。
        </p>
      </div>
      <StaleBadge :stale="newsStore.stale || marketStore.stale || topicStore.stale" label="全局数据" />
    </header>

    <StatusBanner
      kicker="System"
      :title="connectionStore.state === 'live' ? 'SSE 增量更新正常' : '当前处于降级或断线状态'"
      :tone="connectionStore.state === 'live' ? 'success' : 'warning'"
      :detail="connectionStore.usingMock ? '后端未就绪时已自动使用 mock 兼容层。' : connectionStore.streamError ?? '历史数据仍通过 REST 可用。'"
    />

    <div data-role="dashboard-hero">
      <p class="mb-2.5 text-[11px] uppercase tracking-[0.18em] text-system">Signal Overview</p>
      <HeroMetrics :metrics="metrics" />
    </div>

    <section class="grid gap-[14px] xl:grid-cols-[1.1fr_0.9fr]" data-role="dashboard-grid">
      <SectionCard eyebrow="Topic Radar" title="主题聚合" subtitle="按重要度排序，保留股票和情绪入口">
        <LoadingBlock :loading="topicStore.loading" :empty="topicStore.topTopics.length === 0">
          <TopicBoard :topics="topicStore.topTopics" />
        </LoadingBlock>
      </SectionCard>

      <SectionCard eyebrow="Live Movers" title="自选股异动" subtitle="盘中优先观察异常波动和量能变化">
        <LoadingBlock :loading="marketStore.loading" :empty="marketStore.abnormalMovers.length === 0" empty-text="暂无异动">
          <div class="grid gap-2.5">
            <section
              class="grid gap-1.5 rounded-2xl border border-border bg-white/[0.02] p-4 [background-image:linear-gradient(135deg,rgba(23,104,194,0.16),rgba(6,17,31,0.88))]"
              data-role="movement-summary"
            >
              <div>
                <p class="mb-1.5 text-[11px] uppercase tracking-[0.16em] text-system">Signal Count</p>
                <strong class="block text-2xl leading-[1.1]">{{ marketStore.abnormalMovers.length }} 只异动</strong>
              </div>
              <p class="m-0 text-muted">{{ moverMarketSummary }} · 主因 {{ topMoverReason }}</p>
            </section>

            <article
              v-for="item in moverPreviewItems"
              :key="item.symbol"
              class="flex items-center justify-between gap-3 rounded-2xl border border-border bg-white/[0.03] p-[14px]"
              data-role="movement-preview-item"
            >
              <div class="grid gap-1">
                <strong>{{ item.display_name ?? item.symbol }}</strong>
                <span class="text-muted">{{ item.symbol }} · {{ item.market.toUpperCase() }}</span>
              </div>
              <em class="whitespace-nowrap not-italic text-system">{{ getAbnormalReasonLabel(item.abnormal_reason) }}</em>
            </article>

            <RouterLink
              class="inline-flex min-h-11 items-center justify-center rounded-full border border-[#3aa9f557] bg-[rgba(10,26,42,0.72)] font-semibold text-[#9bd8ff] transition duration-150 ease-out hover:-translate-y-px hover:border-[#3aa9f59e] hover:bg-[rgba(15,39,61,0.92)]"
              to="/watchlist"
            >
              查看全部异动
            </RouterLink>
          </div>
        </LoadingBlock>
      </SectionCard>

      <SectionCard
        class="xl:col-span-2"
        eyebrow="News Wire"
        title="最新新闻"
        subtitle="为 News Feed 提供快速跳转入口"
      >
        <LoadingBlock :loading="newsStore.loading" :empty="newsStore.items.length === 0">
          <div class="grid gap-2.5">
            <article
              v-for="item in newsStore.items.slice(0, 6)"
              :key="item.id"
              class="rounded-2xl border border-border bg-white/[0.03] p-[14px]"
            >
              <div class="mb-2.5 flex gap-2 text-muted">
                <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                <span>{{ item.source_name }}</span>
              </div>
              <strong class="mb-2 block">{{ item.title }}</strong>
              <p class="text-muted">{{ item.summary }}</p>
            </article>
          </div>
        </LoadingBlock>
      </SectionCard>
    </section>
  </div>
</template>
