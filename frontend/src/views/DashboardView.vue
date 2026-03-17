<script setup lang="ts">
import { computed } from 'vue';

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

const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const topicStore = useTopicStore();

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
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Market Control：把连接状态、情绪概览、主题聚合和自选股异动压缩到同一块总览面板里。</p>
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
      <p class="dashboard-label">Signal Overview</p>
      <HeroMetrics :metrics="metrics" />
    </div>

    <section class="dashboard-grid">
      <SectionCard eyebrow="Topic Radar" title="主题聚合" subtitle="按重要度排序，保留股票和情绪入口">
        <LoadingBlock :loading="topicStore.loading" :empty="topicStore.topTopics.length === 0">
          <TopicBoard :topics="topicStore.topTopics" />
        </LoadingBlock>
      </SectionCard>

      <SectionCard eyebrow="Live Movers" title="自选股异动" subtitle="盘中优先观察异常波动和量能变化">
        <LoadingBlock :loading="marketStore.loading" :empty="marketStore.abnormalMovers.length === 0" empty-text="暂无异动">
          <div class="movement-list">
            <article v-for="item in marketStore.abnormalMovers" :key="item.symbol" class="movement-card">
              <strong>{{ item.display_name ?? item.symbol }}</strong>
              <span>{{ item.symbol }} · {{ item.market.toUpperCase() }}</span>
              <em>{{ item.abnormal_reason ?? 'abnormal' }}</em>
            </article>
          </div>
        </LoadingBlock>
      </SectionCard>

      <SectionCard eyebrow="News Wire" title="最新新闻" subtitle="为 News Feed 提供快速跳转入口">
        <LoadingBlock :loading="newsStore.loading" :empty="newsStore.items.length === 0">
          <div class="headline-list">
            <article v-for="item in newsStore.items.slice(0, 6)" :key="item.id" class="headline-card">
              <div class="card-top">
                <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
                <span>{{ item.source_name }}</span>
              </div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.summary }}</p>
            </article>
          </div>
        </LoadingBlock>
      </SectionCard>
    </section>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.dashboard-label {
  margin: 0 0 10px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--system);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 14px;
}

.dashboard-grid > :last-child {
  grid-column: 1 / -1;
}

.movement-list,
.headline-list {
  display: grid;
  gap: 10px;
}

.movement-card,
.headline-card {
  border-radius: 16px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
}

.movement-card span,
.headline-card p,
.card-top {
  color: var(--muted);
}

.card-top {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.headline-card strong {
  display: block;
  margin-bottom: 8px;
}

@media (max-width: 1320px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
