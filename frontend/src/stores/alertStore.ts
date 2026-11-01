import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
import type { Alert } from '../types/api';

// 站内提醒（聚焦改造 P2）：列表 + 未读数。SSE `alert.created` 经 receiveAlert 增量推入；
// 隔夜提醒（静默时段产生）在次日早上才对接口可见，由 AppShell 的定时 refreshUnread 兜底。
export const useAlertStore = defineStore('alertStore', () => {
  const alerts = ref<Alert[]>([]);
  const unread = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const daytimeAlerts = computed(() => alerts.value.filter((alert) => !alert.overnight));
  const overnightAlerts = computed(() => alerts.value.filter((alert) => alert.overnight));

  async function loadAlerts() {
    loading.value = true;
    error.value = null;
    try {
      const response = await apiClient.getAlerts();
      alerts.value = response.data;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '提醒加载失败';
    } finally {
      loading.value = false;
    }
  }

  async function refreshUnread() {
    try {
      const response = await apiClient.getAlertUnreadCount();
      unread.value = response.data.unread;
    } catch {
      // 未读数只是角标，失败时保留上一次的值。
    }
  }

  function receiveAlert(alert: Alert) {
    if (alerts.value.some((item) => item.id === alert.id)) {
      return;
    }
    alerts.value = [alert, ...alerts.value];
    if (!alert.read_at) {
      unread.value += 1;
    }
  }

  async function markRead(id: number) {
    const target = alerts.value.find((alert) => alert.id === id);
    const wasUnread = target ? !target.read_at : false;
    const response = await apiClient.markAlertRead(id);
    alerts.value = alerts.value.map((alert) => (alert.id === id ? response.data : alert));
    if (wasUnread) {
      unread.value = Math.max(0, unread.value - 1);
    }
  }

  async function markAllRead() {
    await apiClient.markAllAlertsRead();
    const now = new Date().toISOString();
    alerts.value = alerts.value.map((alert) => (alert.read_at ? alert : { ...alert, read_at: now }));
    unread.value = 0;
  }

  return {
    alerts,
    unread,
    loading,
    error,
    daytimeAlerts,
    overnightAlerts,
    loadAlerts,
    refreshUnread,
    receiveAlert,
    markRead,
    markAllRead,
  };
});
