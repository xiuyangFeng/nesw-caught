<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

import RouteErrorBoundary from '../common/RouteErrorBoundary.vue';

import { useConnectionStore } from '../../stores/connectionStore';
import { useMarketStore } from '../../stores/marketStore';
import { useNewsStore } from '../../stores/newsStore';
import { useRuntimeStatusStore } from '../../stores/runtimeStatusStore';
import { useTopicStore } from '../../stores/topicStore';
import { useWatchlistStore } from '../../stores/watchlistStore';
import { getRuntimeDiagnostic } from '../../utils/runtimeDiagnostics';
import { formatMarketTime } from '../../utils/time';

const route = useRoute();
const connectionStore = useConnectionStore();
const newsStore = useNewsStore();
const marketStore = useMarketStore();
const runtimeStatusStore = useRuntimeStatusStore();
const topicStore = useTopicStore();
const watchlistStore = useWatchlistStore();
const runtimePollIntervalMs = 60_000;
const runtimePollFreshnessSeconds = 45;
const newsFeedLayoutStreamLimit = 100;
let runtimeStatusPollHandle: ReturnType<typeof setInterval> | null = null;
let shellDisposed = false;

const navItems = [
  { label: 'Latest Events', to: '/news', index: '01' },
  { label: 'Dashboard', to: '/dashboard', index: '02' },
  { label: 'Watchlist', to: '/watchlist', index: '03' },
  { label: 'X Monitor', to: '/x-monitor', index: '04' },
  { label: 'AI Chat', to: '/chat', index: '05' },
  { label: 'LLM Settings', to: '/settings/llm', index: '06' },
  { label: 'Notify', to: '/settings/notify', index: '07' },
  { label: 'Signal Backtest', to: '/analytics/backtest', index: '08' },
  { label: 'Daily Digest', to: '/digest', index: '09' },
  { label: 'Calendar', to: '/calendar', index: '10' },
  { label: 'System Health', to: '/ops', index: '11' },
  { label: 'Portfolio', to: '/portfolio', index: '12' },
  { label: 'Sentiment Eval', to: '/eval/sentiment', index: '13' },
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
      signalClass: 'bg-success shadow-[0_0_10px_rgba(57,200,132,0.38)]',
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
      signalClass: 'bg-danger shadow-[0_0_10px_rgba(255,111,134,0.32)]',
    } as const;
  }
  return {
    label: 'SSE WAIT',
    detail: 'Handshake pending',
    signalClass: 'bg-warning shadow-[0_0_10px_rgba(83,194,255,0.34)]',
  } as const;
});

const marketWorkerSummary = computed(() => {
  const status = runtimeStatusStore.marketWorkerStatus;
  if (!status) {
    return {
      label: 'MARKET WORKER UNKNOWN',
      detail: 'No runtime status',
      toneClass: 'neutral',
      error: null,
    } as const;
  }
  if (status.status === 'ok') {
    return {
      label: `${status.name} OK`,
      detail: `Last success ${formatMarketTime(status.last_success_at ?? status.last_heartbeat_at ?? '', 'hk')} HKT`,
      toneClass: 'success',
      error: null,
    } as const;
  }
  if (status.status === 'degraded') {
    return {
      label: `${status.name} DEGRADED`,
      detail: `Last success ${status.last_success_at ? formatMarketTime(status.last_success_at, 'hk') : '--'} HKT`,
      toneClass: 'warning',
      error: status.last_error,
    } as const;
  }
  return {
    label: `${status.name} ${status.status.toUpperCase()}`,
    detail: 'Runtime status available',
    toneClass: 'neutral',
    error: status.last_error,
  } as const;
});

const runtimeDiagnostic = computed(() =>
  getRuntimeDiagnostic({
    connectionState: connectionStore.state,
    streamStatus: runtimeStatusStore.streamStatus,
    usingMock: runtimeStatusStore.usingMock,
    marketWorkerStatus: runtimeStatusStore.marketWorkerStatus,
  }),
);

function runtimeDiagnosticToneClass(tone: 'success' | 'warning' | 'danger' | 'default') {
  if (tone === 'danger') {
    return 'text-danger';
  }
  if (tone === 'warning') {
    return 'text-warning';
  }
  if (tone === 'success') {
    return 'text-success';
  }
  return 'text-text-soft';
}

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

function stopRuntimeStatusPolling() {
  if (runtimeStatusPollHandle === null) {
    return;
  }
  clearInterval(runtimeStatusPollHandle);
  runtimeStatusPollHandle = null;
}

function refreshNewsFeedLayoutIfVisible() {
  if (!route.path.startsWith('/news')) {
    return;
  }
  const market = newsStore.feedQuery?.market || undefined;
  void newsStore.loadFeedLayout({
    market,
    limit_events: 6,
    limit_topics: 6,
    limit_stream: newsFeedLayoutStreamLimit,
  });
}

function startRuntimeStatusPolling() {
  stopRuntimeStatusPolling();
  runtimeStatusPollHandle = setInterval(() => {
    void runtimeStatusStore.loadRuntimeStatusIfStale(runtimePollFreshnessSeconds);
  }, runtimePollIntervalMs);
}

async function bootstrap() {
  await runtimeStatusStore.loadRuntimeStatus();
  if (shellDisposed) {
    return;
  }
  connectionStore.applyStreamStatus(runtimeStatusStore.streamStatus, runtimeStatusStore.usingMock);

  await Promise.all([
    newsStore.loadDashboardNews({ limit: 200 }),
    newsStore.loadNewsRuntime(),
    marketStore.loadSnapshots(),
    topicStore.loadTopics(),
    watchlistStore.loadWatchlist(),
  ]);
  if (shellDisposed) {
    return;
  }

  startRuntimeStatusPolling();

  connectionStore.connect((event) => {
    if (event.type === 'news.created') {
      newsStore.upsertNews(event.payload);
      refreshNewsFeedLayoutIfVisible();
      return;
    }
    if (event.type === 'news.updated') {
      newsStore.upsertNewsUpdate(event.payload);
      refreshNewsFeedLayoutIfVisible();
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
      refreshNewsFeedLayoutIfVisible();
      return;
    }
    if (event.type === 'watchlist.movement') {
      marketStore.upsertSnapshot(event.payload);
      void runtimeStatusStore.loadRuntimeStatusIfStale();
      return;
    }
    if (event.type === 'stream.keepalive') {
      void runtimeStatusStore.loadRuntimeStatusIfStale();
    }
  });

  void newsStore.refreshDashboardNews().then(async (refreshed) => {
    if (refreshed) {
      await topicStore.loadTopics();
    }
  });
}

onMounted(() => {
  shellDisposed = false;
  void bootstrap();
});

onBeforeUnmount(() => {
  shellDisposed = true;
  stopRuntimeStatusPolling();
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
            Discovery
          </span>
          <small class="text-[11px] uppercase tracking-[0.12em] text-[#8ea0b5]">/ Events / Evidence</small>
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
          <div class="grid grid-cols-1 gap-2" data-role="system-status-unit">
            <strong class="text-[11px] uppercase tracking-[0.16em] text-text">System Status</strong>
            <span class="pill w-full justify-start text-left leading-tight" :class="isLiveConnection ? 'success' : 'neutral'">
              {{ connectionSummary }}
            </span>
          </div>
          <span class="font-mono text-[11px] uppercase tracking-[0.14em] text-text-soft">Feed heartbeat</span>
          <small class="uppercase tracking-[0.08em]">
            Last event:
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </small>
          <div class="grid gap-1.5 border-t border-border/70 pt-2" data-role="market-worker-shell-status">
            <div class="grid grid-cols-1 gap-2" data-role="market-worker-status-unit">
              <span class="font-mono text-[11px] uppercase tracking-[0.14em] text-text-soft">Market worker</span>
              <span
                class="pill w-full justify-start text-left leading-tight"
                :class="marketWorkerSummary.toneClass"
                data-role="market-worker-pill"
              >
                {{ marketWorkerSummary.label }}
              </span>
            </div>
            <small class="uppercase tracking-[0.08em]">{{ marketWorkerSummary.detail }}</small>
            <small v-if="marketWorkerSummary.error" class="uppercase tracking-[0.08em] text-danger">
              Error: {{ marketWorkerSummary.error }}
            </small>
            <div class="grid gap-1 border-t border-border/60 pt-2">
              <strong
                class="text-[11px] uppercase tracking-[0.14em]"
                :class="runtimeDiagnosticToneClass(runtimeDiagnostic.tone)"
                data-role="runtime-diagnostic-headline"
              >
                {{ runtimeDiagnostic.headline }}
              </strong>
              <small class="text-text-soft" data-role="runtime-diagnostic-detail">{{ runtimeDiagnostic.detail }}</small>
              <RouterLink
                v-if="runtimeDiagnostic.actionTarget === 'watchlist'"
                to="/watchlist"
                class="text-[11px] uppercase tracking-[0.14em] text-[#ffca97]"
                data-role="runtime-diagnostic-action"
              >
                {{ runtimeDiagnostic.actionLabel }}
              </RouterLink>
              <small
                v-else
                class="text-[11px] uppercase tracking-[0.14em] text-[#8ea0b5]"
                data-role="runtime-diagnostic-action"
              >
                {{ runtimeDiagnostic.actionLabel }}
              </small>
            </div>
          </div>
          <small class="uppercase tracking-[0.08em]">Workspace latest-event discovery</small>
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
          <span>Workspace latest-event discovery</span>
        </div>
      </section>

      <RouteErrorBoundary>
        <RouterView />
      </RouteErrorBoundary>
    </main>
  </div>
</template>
