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
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'News Feed', to: '/news' },
  { label: 'Watchlist', to: '/watchlist' },
  { label: 'X Monitor', to: '/x-monitor' },
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
      <div class="brand">
        <p>News Caught</p>
        <span>港美股消息跟踪台</span>
      </div>
      <nav>
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <span class="pill" :class="connectionStore.state === 'live' ? 'positive' : 'neutral'">
          {{ connectionSummary }}
        </span>
        <small>
          最近事件:
          {{ connectionStore.lastEventAt ? formatMarketTime(connectionStore.lastEventAt, 'hk') : '--' }}
          HKT
        </small>
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
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 18px;
  min-height: 100vh;
  padding: 18px;
}

.sidebar {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-radius: 28px;
  padding: 22px 18px;
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

nav {
  display: grid;
  gap: 10px;
  margin-top: 32px;
}

.nav-link {
  display: block;
  border-radius: 16px;
  padding: 14px 16px;
  font-weight: 600;
  color: var(--muted);
}

.nav-link.active {
  background: #17130f;
  color: #fffaf0;
}

.sidebar-foot {
  display: grid;
  gap: 10px;
  color: var(--muted);
  font-size: 12px;
}

.main-content {
  min-width: 0;
}
</style>
