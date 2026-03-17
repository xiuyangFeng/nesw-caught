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
      <div class="sidebar-top">
        <div class="brand">
          <p>News Caught</p>
          <span>港美股消息跟踪台</span>
        </div>
        <div class="sidebar-intro">
          <strong>Editor&apos;s Desk</strong>
          <small>按主题热度、事件节奏和市场动向安排阅读顺序。</small>
        </div>
      </div>
      <nav class="nav-group">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to }"
        >
          <span class="nav-index">{{ item.index }}</span>
          <span class="nav-text">{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <div class="status-card">
          <span class="pill" :class="connectionStore.state === 'live' ? 'positive' : 'neutral'">
            {{ connectionSummary }}
          </span>
          <small>
            最近事件:
            {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
            HKT
          </small>
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
  grid-template-columns: 256px minmax(0, 1fr);
  gap: 20px;
  min-height: 100vh;
  padding: 20px;
}

.sidebar {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 24px;
  border-radius: 32px;
  padding: 24px 18px 18px;
  position: sticky;
  top: 20px;
  min-height: calc(100vh - 40px);
}

.sidebar-top {
  display: grid;
  gap: 18px;
}

.brand p {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
}

.brand span {
  color: var(--muted);
  font-size: 13px;
}

.sidebar-intro {
  display: grid;
  gap: 6px;
  padding: 14px 14px 0;
  border-top: 1px solid var(--border);
}

.sidebar-intro strong {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--neutral);
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
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 18px;
  padding: 14px 14px;
  font-weight: 600;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.38);
  border: 1px solid transparent;
}

.nav-index {
  min-width: 24px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: rgba(111, 103, 92, 0.82);
}

.nav-text {
  font-size: 17px;
}

.nav-link.active {
  background: #17130f;
  color: #fffaf0;
  border-color: rgba(255, 250, 240, 0.08);
}

.nav-link.active .nav-index {
  color: rgba(255, 250, 240, 0.72);
}

.sidebar-foot {
  margin-top: auto;
}

.status-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.44);
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
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
