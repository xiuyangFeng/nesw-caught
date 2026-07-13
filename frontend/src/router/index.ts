import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/news',
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
      path: '/news/events/:eventKey',
      name: 'event-detail',
      component: () => import('../views/EventDetailView.vue'),
    },
    {
      path: '/news/:id',
      name: 'news-detail',
      component: () => import('../views/NewsDetailView.vue'),
    },
    {
      path: '/news/sentiment/:sentiment',
      name: 'sentiment-news',
      component: () => import('../views/SentimentNewsView.vue'),
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
      path: '/chat',
      name: 'ai-chat',
      component: () => import('../views/ChatView.vue'),
    },
    {
      path: '/topics/:id',
      name: 'topic-detail',
      component: () => import('../views/TopicDetailView.vue'),
    },
    {
      path: '/analytics/backtest',
      name: 'signal-backtest',
      component: () => import('../views/SignalBacktestView.vue'),
    },
    {
      path: '/ops',
      name: 'ops-health',
      component: () => import('../views/OpsHealthView.vue'),
    },
  ],
});

export default router;
