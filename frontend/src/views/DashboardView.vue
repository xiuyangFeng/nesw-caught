<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import BreakingNewsSpotlight from '../components/dashboard/BreakingNewsSpotlight.vue';
import { computeHourlyTrend } from '../components/dashboard/dashboardTrend';
import DashboardFilterBar from '../components/dashboard/DashboardFilterBar.vue';
import DashboardHeader from '../components/dashboard/DashboardHeader.vue';
import DashboardMoversColumn from '../components/dashboard/DashboardMoversColumn.vue';
import DashboardNewsFeedColumn from '../components/dashboard/DashboardNewsFeedColumn.vue';
import DashboardTopicColumn from '../components/dashboard/DashboardTopicColumn.vue';
import FearGreedPanel from '../components/dashboard/FearGreedPanel.vue';
import HeroMetrics from '../components/dashboard/HeroMetrics.vue';
import MarketTickerStrip from '../components/dashboard/MarketTickerStrip.vue';
import SentimentGauge from '../components/dashboard/SentimentGauge.vue';
import SentimentTrendChart from '../components/dashboard/SentimentTrendChart.vue';
import NewsDetailDrawer from '../components/news/NewsDetailDrawer.vue';
import { useConnectionStore } from '../stores/connectionStore';
import { useMarketOverviewStore } from '../stores/marketOverviewStore';
import { useMarketStore } from '../stores/marketStore';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import type { Market } from '../types/api';

const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const marketOverviewStore = useMarketOverviewStore();
const topicStore = useTopicStore();
const router = useRouter();

// 市场总览(恐慌贪婪指数 + 指数行情条):首载 + 60s 定时刷新,与 WatchlistView 同一模式。
onMounted(() => {
  void marketOverviewStore.loadOverview();
  marketOverviewStore.startAutoRefresh();
});

onUnmounted(() => {
  marketOverviewStore.stopAutoRefresh();
});

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

// 4. 过滤主题
const filteredTopics = computed(() => {
  if (!selectedMarket.value) {
    return topicStore.topTopics;
  }
  return topicStore.topTopics.filter((item) => item.market === selectedMarket.value);
});

// 抽屉交互函数
function openNewsDrawer(id: number) {
  selectedNewsId.value = id;
  drawerVisible.value = true;
}

function closeNewsDrawer() {
  drawerVisible.value = false;
  selectedNewsId.value = null;
}

function changeNewsInDrawer(id: number) {
  selectedNewsId.value = id;
}

// 24小时情绪走势计算数据
const positive24hTrend = computed(() =>
  computeHourlyTrend(filteredDashboardItems.value, 24, (item) => item.sentiment_label === 'positive')
);
const negative24hTrend = computed(() =>
  computeHourlyTrend(filteredDashboardItems.value, 24, (item) => item.sentiment_label === 'negative')
);

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
      trend: computeHourlyTrend(filteredDashboardItems.value, 12),
    },
    {
      label: '偏利好',
      value: String(positive),
      note: '利好情感量',
      tone: 'positive' as const,
      to: '/news/sentiment/positive',
      trend: computeHourlyTrend(filteredDashboardItems.value, 12, (item) => item.sentiment_label === 'positive'),
    },
    {
      label: '偏利空',
      value: String(negative),
      note: '风险侧消息量',
      tone: 'negative' as const,
      to: '/news/sentiment/negative',
      trend: computeHourlyTrend(filteredDashboardItems.value, 12, (item) => item.sentiment_label === 'negative'),
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
    <DashboardHeader
      :status="dashboardStatus"
      :stale="newsStore.dashboardStale || marketStore.stale || topicStore.stale"
    />

    <!-- 顶部突发利好/利空警报横幅 -->
    <BreakingNewsSpotlight :newsItems="filteredDashboardItems" @selectNews="openNewsDrawer" />

    <!-- 全球指数动态行情条(无缝滚动 + 涨跌闪烁) -->
    <MarketTickerStrip />

    <!-- 舆情偏好罗盘与指标网格 -->
    <div data-role="dashboard-hero" class="grid gap-3.5 xl:grid-cols-[1.1fr_1.8fr_2.1fr]">
      <SentimentGauge :positiveCount="positiveCount" :negativeCount="negativeCount" />

      <SentimentTrendChart :positiveTrend="positive24hTrend" :negativeTrend="negative24hTrend" />

      <div class="flex flex-col justify-between gap-3.5">
        <DashboardFilterBar
          v-model:selectedMarket="selectedMarket"
          v-model:selectedSentiment="selectedSentiment"
          :markets="markets"
          :sentiments="sentiments"
        />

        <HeroMetrics :metrics="metrics" class="flex-grow" />
      </div>
    </div>

    <section class="grid gap-[14px] xl:grid-cols-[1.35fr_1fr_0.72fr]" data-role="dashboard-columns">
      <DashboardNewsFeedColumn
        :items="filteredDashboardItems"
        :loading="newsStore.dashboardLoading"
        @selectNews="openNewsDrawer"
      />

      <DashboardTopicColumn :topics="filteredTopics" :loading="topicStore.loading" />

      <DashboardMoversColumn :movers="filteredMovers" :loading="marketStore.loading" />
    </section>

    <!-- 市场情绪与恐慌指数(替代原来源健康区块) -->
    <FearGreedPanel />

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
