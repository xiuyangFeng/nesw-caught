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
      path: '/x-monitor',
      name: 'x-monitor',
      component: () => import('../views/XMonitorView.vue'),
    },
    {
      path: '/topics/:id',
      name: 'topic-detail',
      component: () => import('../views/TopicDetailView.vue'),
    },
  ],
});

export default router;
