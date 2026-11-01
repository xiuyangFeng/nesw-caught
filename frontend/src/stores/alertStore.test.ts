import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Alert } from '../types/api';

const apiClient = {
  getAlerts: vi.fn(),
  getAlertUnreadCount: vi.fn(),
  markAlertRead: vi.fn(),
  markAllAlertsRead: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

function buildAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 1,
    kind: 'holding_price_move',
    severity: 'immediate',
    symbol: '688256.SH',
    title: '寒武纪 涨 6.10%',
    body: '现价 106.10（昨收 100.00）',
    payload: {},
    overnight: false,
    created_at: '2026-11-02T02:00:00Z',
    visible_at: '2026-11-02T02:00:00Z',
    read_at: null,
    ...overrides,
  };
}

async function freshStore() {
  const { createPinia, setActivePinia } = await import('pinia');
  const { useAlertStore } = await import('./alertStore');
  setActivePinia(createPinia());
  return useAlertStore();
}

describe('alertStore', () => {
  beforeEach(() => {
    Object.values(apiClient).forEach((fn) => fn.mockReset());
  });

  it('loads alerts and splits overnight ones into their own group', async () => {
    apiClient.getAlerts.mockResolvedValue({
      data: [buildAlert({ id: 2 }), buildAlert({ id: 1, overnight: true, title: '隔夜：东山精密公告' })],
      degraded: false,
    });
    const store = await freshStore();

    await store.loadAlerts();

    expect(store.alerts).toHaveLength(2);
    expect(store.daytimeAlerts.map((alert) => alert.id)).toEqual([2]);
    expect(store.overnightAlerts.map((alert) => alert.id)).toEqual([1]);
    expect(store.error).toBeNull();
  });

  it('refreshes the unread count', async () => {
    apiClient.getAlertUnreadCount.mockResolvedValue({ data: { unread: 3 }, degraded: false });
    const store = await freshStore();

    await store.refreshUnread();

    expect(store.unread).toBe(3);
  });

  it('prepends pushed alerts once and bumps the unread count', async () => {
    const store = await freshStore();

    store.receiveAlert(buildAlert({ id: 7 }));
    store.receiveAlert(buildAlert({ id: 7 }));

    expect(store.alerts.map((alert) => alert.id)).toEqual([7]);
    expect(store.unread).toBe(1);
  });

  it('marks a single alert read and decrements unread', async () => {
    apiClient.getAlerts.mockResolvedValue({ data: [buildAlert({ id: 5 })], degraded: false });
    apiClient.getAlertUnreadCount.mockResolvedValue({ data: { unread: 1 }, degraded: false });
    apiClient.markAlertRead.mockResolvedValue({
      data: buildAlert({ id: 5, read_at: '2026-11-02T03:00:00Z' }),
      degraded: false,
    });
    const store = await freshStore();
    await store.loadAlerts();
    await store.refreshUnread();

    await store.markRead(5);

    expect(apiClient.markAlertRead).toHaveBeenCalledWith(5);
    expect(store.alerts[0].read_at).toBe('2026-11-02T03:00:00Z');
    expect(store.unread).toBe(0);
  });

  it('marks everything read', async () => {
    apiClient.getAlerts.mockResolvedValue({ data: [buildAlert({ id: 1 }), buildAlert({ id: 2 })], degraded: false });
    apiClient.markAllAlertsRead.mockResolvedValue({ data: { updated: 2 }, degraded: false });
    const store = await freshStore();
    await store.loadAlerts();

    await store.markAllRead();

    expect(store.alerts.every((alert) => alert.read_at !== null)).toBe(true);
    expect(store.unread).toBe(0);
  });
});
