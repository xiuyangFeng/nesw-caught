import { createRouter, createWebHistory } from 'vue-router';

import { isDynamicImportError, lazyView, recoverFromChunkError } from '../utils/lazyImport';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/desk',
    },
    {
      path: '/desk',
      name: 'desk',
      component: lazyView(() => import('../views/DeskView.vue')),
    },
    {
      path: '/desk/ops',
      name: 'desk-ops',
      component: lazyView(() => import('../views/DeskOpsView.vue')),
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: lazyView(() => import('../views/DashboardView.vue')),
    },
    {
      path: '/news',
      name: 'news-feed',
      component: lazyView(() => import('../views/NewsFeedView.vue')),
    },
    {
      path: '/news/events/:eventKey',
      name: 'event-detail',
      component: lazyView(() => import('../views/EventDetailView.vue')),
    },
    {
      path: '/news/:id',
      name: 'news-detail',
      component: lazyView(() => import('../views/NewsDetailView.vue')),
    },
    {
      path: '/news/sentiment/:sentiment',
      name: 'sentiment-news',
      component: lazyView(() => import('../views/SentimentNewsView.vue')),
    },
    {
      path: '/watchlist',
      name: 'watchlist',
      component: lazyView(() => import('../views/WatchlistView.vue')),
    },
    {
      path: '/watchlist/:symbol',
      name: 'watchlist-detail',
      component: lazyView(() => import('../views/WatchlistDetailView.vue')),
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: lazyView(() => import('../views/PortfolioView.vue')),
    },
    {
      path: '/x-monitor',
      name: 'x-monitor',
      component: lazyView(() => import('../views/XMonitorView.vue')),
    },
    {
      path: '/calendar',
      name: 'event-calendar',
      component: lazyView(() => import('../views/CalendarView.vue')),
    },
    {
      path: '/settings/llm',
      name: 'llm-settings',
      component: lazyView(() => import('../views/LlmSettingsView.vue')),
    },
    {
      path: '/settings/notify',
      name: 'notify-settings',
      component: lazyView(() => import('../views/NotifySettingsView.vue')),
    },
    {
      path: '/chat',
      name: 'ai-chat',
      component: lazyView(() => import('../views/ChatView.vue')),
    },
    {
      path: '/digest',
      name: 'daily-digest',
      component: lazyView(() => import('../views/DigestView.vue')),
    },
    {
      path: '/topics/:id',
      name: 'topic-detail',
      component: lazyView(() => import('../views/TopicDetailView.vue')),
    },
    {
      path: '/analytics/backtest',
      name: 'signal-backtest',
      component: lazyView(() => import('../views/SignalBacktestView.vue')),
    },
    {
      path: '/ops',
      name: 'ops-health',
      component: lazyView(() => import('../views/OpsHealthView.vue')),
    },
    {
      path: '/eval/sentiment',
      name: 'sentiment-eval',
      component: lazyView(() => import('../views/SentimentEvalView.vue')),
    },
  ],
});

// If a route view's chunk still fails to load after the loader's own retry
// (e.g. stale hashes after a redeploy), recover with a controlled reload to the
// intended path instead of leaving the user on a frozen, half-navigated page.
router.onError((error, to) => {
  if (isDynamicImportError(error)) {
    recoverFromChunkError(() => {
      window.location.assign(to?.fullPath ?? window.location.href);
    });
  }
});

export default router;
