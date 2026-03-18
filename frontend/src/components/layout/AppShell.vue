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
  <div class="shell">
    <aside class="surface sidebar">
      <div class="sidebar-top" data-role="system-header">
        <div class="brand">
          <p>NEWS CAUGHT</p>
          <span>Market Intelligence Terminal</span>
        </div>
        <div class="sidebar-intro">
          <strong>System Desk</strong>
          <small>跟踪新闻、主题热度、自选股异动与流式连接状态。</small>
        </div>
      </div>
      <nav class="nav-group" data-role="primary-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to }"
          :data-route-active="route.path === item.to ? 'true' : 'false'"
        >
          <span v-if="route.path === item.to" class="nav-signal" data-role="nav-active-signal" />
          <span class="nav-index">{{ item.index }}</span>
          <span class="nav-copy">
            <span class="nav-text">{{ item.label }}</span>
            <span class="nav-meta">MODULE</span>
          </span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot" data-role="system-status">
        <div class="status-card">
          <div class="status-label-row">
            <strong>System Status</strong>
            <span class="pill" :class="connectionStore.state === 'live' ? 'positive' : 'neutral'">
              {{ connectionSummary }}
            </span>
          </div>
          <span class="status-line">
            Feed heartbeat
          </span>
          <small>
            最近事件:
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </small>
          <small>Workspace: multi-market watch</small>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  gap: 18px;
  min-height: 100vh;
  padding: 18px;
}

.sidebar {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 22px;
  border-radius: 24px;
  padding: 20px 16px 16px;
  position: sticky;
  top: 18px;
  min-height: calc(100vh - 36px);
}

.sidebar-top {
  display: grid;
  gap: 16px;
}

.brand p {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.brand span {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.sidebar-intro {
  display: grid;
  gap: 6px;
  padding: 14px 0 0;
  border-top: 1px solid var(--border);
}

.sidebar-intro strong {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--system, var(--neutral));
}

.sidebar-intro small {
  color: var(--muted);
  line-height: 1.6;
}

.nav-group {
  display: grid;
  gap: 8px;
}

.nav-link {
  position: relative;
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: center;
  gap: 12px;
  border-radius: 16px;
  padding: 13px 14px;
  font-weight: 600;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid transparent;
  transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(125, 211, 252, 0.12);
  transform: translateX(2px);
}

.nav-signal {
  width: 3px;
  height: 26px;
  border-radius: 999px;
  background: var(--accent, #ff9f2f);
  box-shadow: 0 0 18px rgba(255, 159, 47, 0.35);
}

.nav-index {
  min-width: 24px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: rgba(127, 142, 163, 0.88);
  font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
}

.nav-copy {
  display: grid;
  gap: 2px;
}

.nav-text {
  font-size: 16px;
  color: var(--text);
}

.nav-meta {
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--muted);
}

.nav-link.active {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  border-color: var(--border);
}

.nav-link.active .nav-index,
.nav-link.active .nav-meta {
  color: var(--text-soft, rgba(243, 247, 251, 0.72));
}

.sidebar-foot {
  margin-top: auto;
}

.status-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
}

.status-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-label-row strong {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--text);
}

.status-line {
  font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
  font-size: 12px;
  color: var(--text-soft, rgba(243, 247, 251, 0.78));
}

.main-content {
  min-width: 0;
}

@media (max-width: 1100px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
    min-height: auto;
  }
}
</style>
