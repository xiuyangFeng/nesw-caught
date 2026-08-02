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
const feedLayoutDebounceMs = 500;
// layout 全量刷新只走低频轮询：news.created/updated 已由 store 本地增量覆盖,
// 只有 topic.updated(结构变化无法本地增量)与周期兜底才触发全量。
const feedLayoutPollIntervalMs = 60_000;
const newsRefreshPollIntervalMs = 5 * 60_000;
// 行情轮询兜底：正常情况下价格走 SSE 的 market.watchlist_refreshed 推送
// （后端 producer 盘中 15s 一轮）。这个定时器只负责补两种漏：SSE 断线期间，
// 以及慢客户端被有界队列丢弃事件的情况。命中的是纯本地快照查询
// /api/market/watchlist，不触发外网抓取，因此 30s 一次的代价可以忽略。
const quotesPollIntervalMs = 30_000;
let runtimeStatusPollHandle: ReturnType<typeof setInterval> | null = null;
let feedLayoutPollHandle: ReturnType<typeof setInterval> | null = null;
let newsRefreshPollHandle: ReturnType<typeof setInterval> | null = null;
let quotesPollHandle: ReturnType<typeof setInterval> | null = null;
let feedLayoutDebounceHandle: ReturnType<typeof setTimeout> | null = null;
let shellDisposed = false;

type NavGroup = {
  title: string;
  ai?: boolean;
  items: { label: string; en: string; to: string }[];
};

const navGroups: NavGroup[] = [
  {
    title: '情报',
    items: [
      { label: '最新事件', en: 'Events', to: '/news' },
      { label: '仪表盘', en: 'Dashboard', to: '/dashboard' },
      { label: '每日复盘', en: 'Digest', to: '/digest' },
      { label: '日历', en: 'Calendar', to: '/calendar' },
    ],
  },
  {
    title: '交易',
    items: [
      { label: '自选股', en: 'Watchlist', to: '/watchlist' },
      { label: '组合', en: 'Portfolio', to: '/portfolio' },
      { label: '信号回测', en: 'Backtest', to: '/analytics/backtest' },
    ],
  },
  {
    title: '智能',
    ai: true,
    items: [
      { label: 'AI 对话', en: 'AI Chat', to: '/chat' },
      { label: 'X 监控', en: 'X Monitor', to: '/x-monitor' },
    ],
  },
  {
    title: '系统',
    items: [
      { label: '模型设置', en: 'LLM', to: '/settings/llm' },
      { label: '通知', en: 'Notify', to: '/settings/notify' },
      { label: '情绪评测', en: 'Eval', to: '/eval/sentiment' },
      { label: '系统健康', en: 'Health', to: '/ops' },
    ],
  },
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
      detail: '实时流畅',
      signalClass: 'bg-success',
      pulse: true,
    } as const;
  }
  if (connectionStore.state === 'degraded') {
    return {
      label: 'SSE DEGRADED',
      detail: '降级至 Mock',
      signalClass: 'bg-warning shadow-[0_0_10px_color-mix(in_srgb,var(--warning)_34%,transparent)]',
      pulse: false,
    } as const;
  }
  if (connectionStore.state === 'offline') {
    return {
      label: 'SSE OFF',
      detail: '重连待机',
      signalClass: 'bg-danger shadow-[0_0_10px_color-mix(in_srgb,var(--danger)_32%,transparent)]',
      pulse: false,
    } as const;
  }
  return {
    label: 'SSE WAIT',
    detail: '握手中',
    signalClass: 'bg-warning shadow-[0_0_10px_color-mix(in_srgb,var(--warning)_34%,transparent)]',
    pulse: false,
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
    'relative flex items-center gap-2.5 rounded-md border py-2.5 pl-4 pr-3',
    'font-medium transition duration-150 ease-out',
    isActive
      ? 'border-transparent bg-[var(--accent-soft)] text-accent'
      : 'border-transparent text-muted hover:translate-x-0.5 hover:bg-[var(--interactive-hover)] hover:text-text-soft',
  ];
}

function stopRuntimeStatusPolling() {
  if (runtimeStatusPollHandle === null) {
    return;
  }
  clearInterval(runtimeStatusPollHandle);
  runtimeStatusPollHandle = null;
}

function refreshNewsFeedLayout() {
  if (shellDisposed || !route.path.startsWith('/news')) {
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

function scheduleNewsFeedLayoutRefresh() {
  if (!route.path.startsWith('/news')) {
    return;
  }
  if (feedLayoutDebounceHandle !== null) {
    clearTimeout(feedLayoutDebounceHandle);
  }
  feedLayoutDebounceHandle = setTimeout(() => {
    feedLayoutDebounceHandle = null;
    refreshNewsFeedLayout();
  }, feedLayoutDebounceMs);
}

function stopFeedLayoutPolling() {
  if (feedLayoutPollHandle === null) {
    return;
  }
  clearInterval(feedLayoutPollHandle);
  feedLayoutPollHandle = null;
}

function startFeedLayoutPolling() {
  stopFeedLayoutPolling();
  feedLayoutPollHandle = setInterval(refreshNewsFeedLayout, feedLayoutPollIntervalMs);
}

function triggerNewsRefresh() {
  if (shellDisposed) {
    return;
  }
  void newsStore.refreshDashboardNews();
}

function stopNewsRefreshPolling() {
  if (newsRefreshPollHandle === null) {
    return;
  }
  clearInterval(newsRefreshPollHandle);
  newsRefreshPollHandle = null;
}

function startNewsRefreshPolling() {
  stopNewsRefreshPolling();
  newsRefreshPollHandle = setInterval(triggerNewsRefresh, newsRefreshPollIntervalMs);
}

function triggerQuotesRefresh() {
  if (shellDisposed) {
    return;
  }
  void watchlistStore.refreshQuotes();
}

function stopQuotesPolling() {
  if (quotesPollHandle === null) {
    return;
  }
  clearInterval(quotesPollHandle);
  quotesPollHandle = null;
}

function startQuotesPolling() {
  stopQuotesPolling();
  quotesPollHandle = setInterval(triggerQuotesRefresh, quotesPollIntervalMs);
}

function handleVisibilityChange() {
  if (shellDisposed) {
    return;
  }
  if (document.visibilityState === 'visible') {
    triggerNewsRefresh();
    startNewsRefreshPolling();
    // 后台期间没有轮询、SSE 也可能已被浏览器挂起，切回前台先补一次，
    // 否则用户会先看到切走时的旧价格、等满一个轮询周期才刷新。
    triggerQuotesRefresh();
    startQuotesPolling();
  } else {
    stopNewsRefreshPolling();
    stopQuotesPolling();
  }
}

function reconcileNewsSnapshot() {
  if (shellDisposed) {
    return;
  }
  void newsStore.loadDashboardNews({ limit: 200 });
  void newsStore.loadNewsRuntime();
  scheduleNewsFeedLayoutRefresh();
}

function startRuntimeStatusPolling() {
  stopRuntimeStatusPolling();
  runtimeStatusPollHandle = setInterval(() => {
    void runtimeStatusStore.loadRuntimeStatusIfStale(runtimePollFreshnessSeconds);
  }, runtimePollIntervalMs);
}

async function bootstrap() {
  triggerNewsRefresh();
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
  startFeedLayoutPolling();
  document.addEventListener('visibilitychange', handleVisibilityChange);
  if (document.visibilityState === 'visible') {
    startNewsRefreshPolling();
    startQuotesPolling();
  }

  connectionStore.connect(
    (event) => {
      if (event.type === 'news.created') {
        // 只走 store 本地增量(feedItems/layout stream 均已覆盖),不再触发 layout 全量刷新
        newsStore.upsertNews(event.payload);
        return;
      }
      if (event.type === 'news.updated') {
        // 单条字段更新同样本地增量,sort/文案变化由 store 替换数组引用驱动视图
        newsStore.upsertNewsUpdate(event.payload);
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
        // topic 结构变化本地无法增量,防抖后全量刷新 layout
        scheduleNewsFeedLayoutRefresh();
        return;
      }
      if (event.type === 'watchlist.movement') {
        marketStore.upsertSnapshot(event.payload);
        void runtimeStatusStore.loadRuntimeStatusIfStale();
        return;
      }
      if (event.type === 'market.watchlist_refreshed') {
        // MarketQuoteProducer 每轮刷新的批量推送：自选股列表/详情的价格主通道。
        // payload 由后端 SSE 直接透传，这里对形状做一次防御性校验，避免一条
        // 异常事件把整个 handler 打断（handler 抛错会连带影响后续事件处理）。
        const quotes = event.payload?.quotes;
        if (!Array.isArray(quotes) || quotes.length === 0) {
          return;
        }
        watchlistStore.applyQuoteBatch(quotes);
        // 仪表盘的异动榜读的是 marketStore.snapshots，与 watchlist 是两套状态，
        // 需要各自更新。两者字段同构（QuoteSummaryView ⊃ PriceSnapshotView）。
        quotes.forEach((quote) => marketStore.upsertSnapshot(quote));
        return;
      }
      if (event.type === 'stream.keepalive') {
        void runtimeStatusStore.loadRuntimeStatusIfStale();
      }
    },
    { onReconnect: reconcileNewsSnapshot },
  );
}

onMounted(() => {
  shellDisposed = false;
  void bootstrap();
});

onBeforeUnmount(() => {
  shellDisposed = true;
  if (feedLayoutDebounceHandle !== null) {
    clearTimeout(feedLayoutDebounceHandle);
    feedLayoutDebounceHandle = null;
  }
  stopFeedLayoutPolling();
  stopRuntimeStatusPolling();
  stopNewsRefreshPolling();
  stopQuotesPolling();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  connectionStore.disconnect();
});
</script>

<template>
  <div class="grid min-h-screen gap-[18px] p-[18px] shell:grid-cols-[272px_minmax(0,1fr)]">
    <aside
      class="surface top-[18px] flex min-h-[calc(100vh-36px)] flex-col gap-[18px] rounded-lg px-4 pb-4 pt-5 shell:sticky"
    >
      <div class="grid gap-4 border-b border-border pb-4" data-role="system-header">
        <div class="flex items-center gap-2.5">
          <span
            class="flex h-8 w-8 flex-none items-center justify-center rounded-md bg-grad-ai font-mono text-base font-bold text-bg shadow-glow-ai"
          >
            N
          </span>
          <div class="grid gap-0.5">
            <p class="m-0 text-lg font-bold leading-none tracking-tight text-text">NEWS CAUGHT</p>
            <span class="label-mono text-[10px] text-text-faint">Quant Intelligence</span>
          </div>
        </div>
        <div class="grid gap-2" data-role="system-desk-note">
          <span
            class="inline-flex w-fit items-center rounded-full border border-border bg-panel-strong px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted"
            data-role="system-desk-chip"
          >
            Discovery
          </span>
          <small class="label-mono text-[10px] normal-case tracking-[0.12em] text-text-faint">/ Events / Evidence</small>
        </div>
      </div>
      <nav class="grid gap-4" data-role="primary-nav">
        <div v-for="group in navGroups" :key="group.title" class="grid gap-1">
          <p class="label-mono flex items-center gap-1.5 px-2 pb-0.5 text-[10px]">
            <span v-if="group.ai" class="text-ai" aria-hidden="true">✦</span>
            {{ group.title }}
          </p>
          <div class="grid gap-0.5">
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              :class="navLinkClasses(isNavItemActive(item.to))"
              :data-route-active="isNavItemActive(item.to) ? 'true' : 'false'"
            >
              <span
                v-if="isNavItemActive(item.to)"
                class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent shadow-glow"
                data-role="nav-active-signal"
              />
              <span class="flex min-w-0 flex-col gap-0.5">
                <span class="text-sm leading-tight">{{ item.label }}</span>
                <span
                  class="font-mono text-[10px] uppercase tracking-[0.16em]"
                  :class="isNavItemActive(item.to) ? 'text-accent' : 'text-text-faint'"
                >
                  {{ item.en }}
                </span>
              </span>
            </RouterLink>
          </div>
        </div>
      </nav>
      <div class="mt-auto" data-role="system-status">
        <div class="grid gap-2.5 rounded-lg border border-border bg-panel-strong p-3.5 text-xs text-muted">
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
                class="text-[11px] uppercase tracking-[0.14em] text-accent"
                data-role="runtime-diagnostic-action"
              >
                {{ runtimeDiagnostic.actionLabel }}
              </RouterLink>
              <small
                v-else
                class="text-[11px] uppercase tracking-[0.14em] text-muted"
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

    <main class="grid min-w-0 content-start gap-3">
      <section
        class="surface flex min-h-12 items-center justify-between gap-4 rounded-[18px] px-4 py-3"
        data-role="shell-status-rail"
      >
        <div class="flex flex-wrap items-center gap-3">
          <span class="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-soft">
            <span
              class="h-2 w-2 rounded-full"
              :class="[shellStatusRail.signalClass, shellStatusRail.pulse ? 'pulse-dot' : '']"
              :style="
                shellStatusRail.pulse
                  ? { '--pulse-color': 'color-mix(in srgb, var(--success) 35%, transparent)' }
                  : undefined
              "
              data-role="shell-status-rail-signal"
            />
            {{ shellStatusRail.label }}
          </span>
          <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ shellStatusRail.detail }}</span>
          <span
            v-if="newsStore.isRefreshing"
            class="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-accent"
            data-role="news-refresh-indicator"
          >
            <span
              class="h-1.5 w-1.5 rounded-full bg-accent pulse-dot"
              style="--pulse-color: color-mix(in srgb, var(--accent) 35%, transparent)"
            />
            同步中
          </span>
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
