<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

import { useConnectionStore } from '../../stores/connectionStore';
import { useMarketStore } from '../../stores/marketStore';
import { useNewsStore } from '../../stores/newsStore';
import { useTopicStore } from '../../stores/topicStore';
import { useWatchlistStore } from '../../stores/watchlistStore';
import { formatMarketTime } from '../../utils/time';

const route = useRoute();
const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const topicStore = useTopicStore();
const watchlistStore = useWatchlistStore();

const navItems = [
  { label: 'Dashboard', to: '/dashboard', index: '01' },
  { label: 'News Feed', to: '/news', index: '02' },
  { label: 'Watchlist', to: '/watchlist', index: '03' },
  { label: 'X Monitor', to: '/x-monitor', index: '04' },
  { label: 'LLM Settings', to: '/settings/llm', index: '05' },
  { label: 'Notify', to: '/settings/notify', index: '06' },
];

const connectionSummary = computed(() => {
  if (connectionStore.state === 'live') {
    return 'SSE 已连接';
  }
  if (connectionStore.state === 'degraded') {
    return '降级为 mock';
  }
  if (connectionStore.state === 'offline') {
    return 'SSE 已断开';
  }
  if (connectionStore.state === 'connecting') {
    return '连接中';
  }
  return '未连接';
});

const isLiveConnection = computed(() => connectionStore.state === 'live');

function navLinkClasses(isActive: boolean) {
  return [
    'relative grid grid-cols-[auto_auto_minmax(0,1fr)] items-center gap-3 rounded-2xl border px-3.5 py-3.5',
    'bg-white/[0.02] font-semibold text-muted transition duration-150 ease-out',
    'border-transparent hover:translate-x-0.5 hover:border-system/15 hover:bg-white/[0.04]',
    isActive ? 'border-border bg-white/[0.05] text-text' : '',
  ];
}

async function bootstrap() {
  await Promise.all([
    connectionStore.loadStreamStatus(),
    newsStore.loadNews({ limit: 200 }),
    marketStore.loadSnapshots(),
    topicStore.loadTopics(),
    watchlistStore.loadWatchlist(),
  ]);

  connectionStore.connect((event) => {
    if (event.type === 'news.created') {
      newsStore.upsertNews(event.payload);
      return;
    }
    if (event.type === 'topic.updated') {
      topicStore.upsertTopic({
        ...event.payload,
        topic_summary: null,
        keywords: [],
        sentiment_label: 'unknown',
        related_symbols: [],
      });
      return;
    }
    if (event.type === 'watchlist.movement') {
      marketStore.upsertSnapshot(event.payload);
    }
  });

  void newsStore.refreshNews().then(async (refreshed) => {
    if (refreshed) {
      await topicStore.loadTopics();
    }
  });
}

onMounted(() => {
  void bootstrap();
});

onBeforeUnmount(() => {
  connectionStore.disconnect();
});
</script>

<template>
  <div class="grid min-h-screen gap-[18px] p-[18px] shell:grid-cols-[272px_minmax(0,1fr)]">
    <aside
      class="surface top-[18px] flex min-h-[calc(100vh-36px)] flex-col gap-[22px] rounded-[24px] px-4 pb-4 pt-5 shell:sticky"
    >
      <div class="grid gap-4" data-role="system-header">
        <div>
          <p class="m-0 text-2xl font-bold tracking-[0.14em]">NEWS CAUGHT</p>
          <span class="text-xs uppercase tracking-[0.12em] text-muted">
            Market Intelligence Terminal
          </span>
        </div>
        <div class="grid gap-1.5 border-t border-border pt-3.5">
          <strong class="text-[11px] uppercase tracking-[0.18em] text-system">System Desk</strong>
          <small class="leading-6 text-muted">跟踪新闻、主题热度、自选股异动与流式连接状态。</small>
        </div>
      </div>
      <nav class="grid gap-2" data-role="primary-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :class="navLinkClasses(route.path === item.to)"
          :data-route-active="route.path === item.to ? 'true' : 'false'"
        >
          <span
            v-if="route.path === item.to"
            class="h-[26px] w-[3px] rounded-full bg-accent shadow-signal"
            data-role="nav-active-signal"
          />
          <span
            class="min-w-6 font-mono text-[11px] tracking-[0.14em]"
            :class="route.path === item.to ? 'text-text-soft' : 'text-[#7f8ea3e0]'"
          >
            {{ item.index }}
          </span>
          <span class="grid gap-0.5">
            <span class="text-base text-text">{{ item.label }}</span>
            <span
              class="text-[10px] tracking-[0.16em]"
              :class="route.path === item.to ? 'text-text-soft' : 'text-muted'"
            >
              MODULE
            </span>
          </span>
        </RouterLink>
      </nav>
      <div class="mt-auto" data-role="system-status">
        <div class="grid gap-2 rounded-[18px] border border-border bg-white/[0.03] p-3.5 text-xs text-muted">
          <div class="flex items-center justify-between gap-3">
            <strong class="text-[11px] uppercase tracking-[0.16em] text-text">System Status</strong>
            <span class="pill" :class="isLiveConnection ? 'positive' : 'neutral'">
              {{ connectionSummary }}
            </span>
          </div>
          <span class="font-mono text-xs text-text-soft">Feed heartbeat</span>
          <small>
            最近事件:
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </small>
          <small>Workspace: multi-market watch</small>
        </div>
      </div>
    </aside>

    <main class="min-w-0">
      <RouterView />
    </main>
  </div>
</template>
