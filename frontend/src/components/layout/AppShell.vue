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

const shellStatusRail = computed(() => {
  if (connectionStore.state === 'live') {
    return {
      label: 'SSE LIVE',
      detail: 'Stream strong',
      signalClass: 'bg-positive shadow-[0_0_10px_rgba(57,200,132,0.38)]',
    } as const;
  }
  if (connectionStore.state === 'degraded') {
    return {
      label: 'SSE DEGRADED',
      detail: 'Mock fallback',
      signalClass: 'bg-warning shadow-[0_0_10px_rgba(83,194,255,0.34)]',
    } as const;
  }
  if (connectionStore.state === 'offline') {
    return {
      label: 'SSE OFF',
      detail: 'Reconnect idle',
      signalClass: 'bg-negative shadow-[0_0_10px_rgba(255,111,134,0.32)]',
    } as const;
  }
  return {
    label: 'SSE WAIT',
    detail: 'Handshake pending',
    signalClass: 'bg-warning shadow-[0_0_10px_rgba(83,194,255,0.34)]',
  } as const;
});

function isNavItemActive(targetPath: string) {
  if (route.path === targetPath) {
    return true;
  }
  if (targetPath === '/news') {
    return route.path.startsWith('/news/');
  }
  if (targetPath === '/watchlist') {
    return route.path.startsWith('/watchlist/');
  }
  if (targetPath === '/dashboard') {
    return route.path.startsWith('/topics/');
  }
  return false;
}

function navLinkClasses(isActive: boolean) {
  return [
    'relative grid grid-cols-[auto_auto_minmax(0,1fr)] items-center gap-3 rounded-[18px] border px-3.5 py-3',
    'bg-white/[0.02] font-semibold text-muted transition duration-150 ease-out',
    'border-transparent hover:translate-x-0.5 hover:border-system/15 hover:bg-white/[0.04]',
    isActive ? 'border-[#ff9f2f33] bg-white/[0.05] text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]' : '',
  ];
}

async function bootstrap() {
  await Promise.all([
    connectionStore.loadStreamStatus(),
    newsStore.loadDashboardNews({ limit: 200 }),
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

  void newsStore.refreshDashboardNews().then(async (refreshed) => {
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
      class="surface top-[18px] flex min-h-[calc(100vh-36px)] flex-col gap-[18px] rounded-[22px] bg-[linear-gradient(180deg,rgba(12,19,30,0.98),rgba(8,14,23,0.98))] px-4 pb-4 pt-5 shell:sticky"
    >
      <div class="grid gap-4 border-b border-border/80 pb-4" data-role="system-header">
        <div>
          <p class="m-0 text-2xl font-bold tracking-[0.14em]">NEWS CAUGHT</p>
          <span class="text-[11px] uppercase tracking-[0.16em] text-muted">
            Market Intelligence Terminal
          </span>
        </div>
        <div class="grid gap-2" data-role="system-desk-note">
          <span
            class="inline-flex w-fit items-center rounded-full border border-border bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted"
            data-role="system-desk-chip"
          >
            Desk
          </span>
          <small class="text-[11px] uppercase tracking-[0.12em] text-[#8ea0b5]">/ News / Topics / Movers</small>
        </div>
      </div>
      <nav class="grid gap-1.5" data-role="primary-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :class="navLinkClasses(isNavItemActive(item.to))"
          :data-route-active="isNavItemActive(item.to) ? 'true' : 'false'"
        >
          <span
            v-if="isNavItemActive(item.to)"
            class="h-[26px] w-[3px] rounded-full bg-accent shadow-signal"
            data-role="nav-active-signal"
          />
          <span
            class="min-w-6 font-mono text-[11px] tracking-[0.14em]"
            :class="isNavItemActive(item.to) ? 'text-[#ffd5b0]' : 'text-[#7f8ea3e0]'"
          >
            {{ item.index }}
          </span>
          <span class="grid gap-0.5">
            <span class="text-[15px] text-text">{{ item.label }}</span>
            <span
              class="text-[10px] uppercase tracking-[0.18em]"
              :class="isNavItemActive(item.to) ? 'text-[#ffb77d]' : 'text-muted'"
            >
              MODULE
            </span>
          </span>
        </RouterLink>
      </nav>
      <div class="mt-auto" data-role="system-status">
        <div class="grid gap-2.5 rounded-[16px] border border-border bg-white/[0.03] p-3.5 text-xs text-muted">
          <div class="flex items-center justify-between gap-3">
            <strong class="text-[11px] uppercase tracking-[0.16em] text-text">System Status</strong>
            <span class="pill" :class="isLiveConnection ? 'positive' : 'neutral'">
              {{ connectionSummary }}
            </span>
          </div>
          <span class="font-mono text-[11px] uppercase tracking-[0.14em] text-text-soft">Feed heartbeat</span>
          <small class="uppercase tracking-[0.08em]">
            Last event:
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </small>
          <small class="uppercase tracking-[0.08em]">Workspace multi-market watch</small>
        </div>
      </div>
    </aside>

    <main class="grid min-w-0 gap-3">
      <section
        class="surface flex min-h-12 items-center justify-between gap-4 rounded-[18px] px-4 py-3"
        data-role="shell-status-rail"
      >
        <div class="flex flex-wrap items-center gap-3">
          <span class="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-soft">
            <span class="h-2 w-2 rounded-full" :class="shellStatusRail.signalClass" data-role="shell-status-rail-signal" />
            {{ shellStatusRail.label }}
          </span>
          <span class="text-[10px] uppercase tracking-[0.16em] text-system">{{ shellStatusRail.detail }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-[0.16em] text-muted">
          <span>
            Last event
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </span>
          <span>Workspace multi-market watch</span>
        </div>
      </section>

      <RouterView />
    </main>
  </div>
</template>
