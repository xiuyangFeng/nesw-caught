import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
    },
    {
      path: '/news',
      name: 'news-feed',
      component: () => import('../views/NewsFeedView.vue'),
    },
    {
      path: '/news/:id',
      name: 'news-detail',
      component: () => import('../views/NewsDetailView.vue'),
    },
    {
      path: '/watchlist',
      name: 'watchlist',
      component: () => import('../views/WatchlistView.vue'),
    },
    {
      path: '/watchlist/:symbol',
      name: 'watchlist-detail',
      component: () => import('../views/WatchlistDetailView.vue'),
    },
    {
      path: '/x-monitor',
      name: 'x-monitor',
      component: () => import('../views/XMonitorView.vue'),
    },
    {
      path: '/settings/llm',
      name: 'llm-settings',
      component: () => import('../views/LlmSettingsView.vue'),
    },
    {
      path: '/settings/notify',
      name: 'notify-settings',
      component: () => import('../views/NotifySettingsView.vue'),
    },
    {
      path: '/topics/:id',
      name: 'topic-detail',
      component: () => import('../views/TopicDetailView.vue'),
    },
  ],
});

export default router;
