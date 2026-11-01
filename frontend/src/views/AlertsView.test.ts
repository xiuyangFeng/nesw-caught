import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Alert } from '../types/api';

const { getAlerts, getAlertUnreadCount, markAlertRead, markAllAlertsRead } = vi.hoisted(() => ({
  getAlerts: vi.fn(),
  getAlertUnreadCount: vi.fn(),
  markAlertRead: vi.fn(),
  markAllAlertsRead: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { getAlerts, getAlertUnreadCount, markAlertRead, markAllAlertsRead },
}));

import AlertsView from './AlertsView.vue';

function buildAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 1,
    kind: 'holding_price_move',
    severity: 'immediate',
    symbol: '688256.SH',
    title: '寒武纪 涨 6.10%',
    body: '现价 106.10（昨收 100.00） · 持仓 100 股',
    payload: {},
    overnight: false,
    created_at: '2026-11-02T02:00:00Z',
    visible_at: '2026-11-02T02:00:00Z',
    read_at: null,
    ...overrides,
  };
}

function mountView() {
  return mount(AlertsView, { global: { stubs: { RouterLink: RouterLinkStub } } });
}

describe('AlertsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    [getAlerts, getAlertUnreadCount, markAlertRead, markAllAlertsRead].forEach((fn) => fn.mockReset());
    getAlertUnreadCount.mockResolvedValue({ data: { unread: 0 }, degraded: false });
  });

  it('shows the empty state when there are no alerts', async () => {
    getAlerts.mockResolvedValue({ data: [], degraded: false });
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.find('[data-role="alerts-empty"]').exists()).toBe(true);
  });

  it('groups daytime and overnight alerts and links each alert to its target', async () => {
    getAlerts.mockResolvedValue({
      data: [
        buildAlert({ id: 3 }),
        buildAlert({
          id: 2,
          kind: 'holding_news',
          symbol: '002384.SZ',
          title: '东山精密：拿下北美大客户新订单',
          payload: { news_id: 101 },
        }),
        buildAlert({ id: 1, kind: 'holding_news', overnight: true, title: '寒武纪：发布公告', payload: { news_id: 55 } }),
      ],
      degraded: false,
    });
    const wrapper = mountView();
    await flushPromises();

    const daytime = wrapper.find('[data-role="alerts-daytime"]');
    const overnight = wrapper.find('[data-role="alerts-overnight"]');
    expect(daytime.findAll('[data-role="alert-item"]')).toHaveLength(2);
    expect(overnight.findAll('[data-role="alert-item"]')).toHaveLength(1);
    expect(daytime.text()).toContain('持仓异动');
    expect(daytime.text()).toContain('持仓新闻');

    const targets = wrapper.findAllComponents(RouterLinkStub).map((link) => link.props('to'));
    expect(targets).toEqual(expect.arrayContaining(['/watchlist/688256.SH', '/news/101', '/news/55']));
  });

  it('marks a single alert read and can mark everything read', async () => {
    getAlerts.mockResolvedValue({ data: [buildAlert({ id: 9 }), buildAlert({ id: 8 })], degraded: false });
    markAlertRead.mockResolvedValue({ data: buildAlert({ id: 9, read_at: '2026-11-02T03:00:00Z' }), degraded: false });
    markAllAlertsRead.mockResolvedValue({ data: { updated: 1 }, degraded: false });
    const wrapper = mountView();
    await flushPromises();

    await wrapper.find('[data-role="alert-mark-read"]').trigger('click');
    await flushPromises();
    expect(markAlertRead).toHaveBeenCalledWith(9);

    await wrapper.find('[data-role="alerts-mark-all-read"]').trigger('click');
    await flushPromises();
    expect(markAllAlertsRead).toHaveBeenCalled();
    expect(wrapper.findAll('[data-role="alert-unread-dot"]')).toHaveLength(0);
  });
});
