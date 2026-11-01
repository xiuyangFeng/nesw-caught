import { createRouter, createWebHistory } from 'vue-router';

import { isDynamicImportError, lazyView, recoverFromChunkError } from '../utils/lazyImport';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      // P1 期间首页临时指向仪表盘；P4 盯盘台上线后替换。
      redirect: '/dashboard',
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
      path: '/alerts',
      name: 'alerts',
      component: lazyView(() => import('../views/AlertsView.vue')),
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
      path: '/ops',
      name: 'ops-health',
      component: lazyView(() => import('../views/OpsHealthView.vue')),
    },
    {
      // 兜底：已下线页面（/desk*、/chat、/x-monitor、/analytics/backtest、/eval/sentiment）
      // 的旧书签及任何未知路径都回到仪表盘，避免空白页。
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard',
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
