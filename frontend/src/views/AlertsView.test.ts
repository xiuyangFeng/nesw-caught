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

  it('labels the AI funnel alert kinds and shows digest item details', async () => {
    getAlerts.mockResolvedValue({
      data: [
        buildAlert({ id: 14, kind: 'overseas_major', symbol: null, title: '海外重大：美联储意外降息', payload: { news_id: 301 } }),
        buildAlert({
          id: 13,
          kind: 'sector_news_digest',
          symbol: null,
          title: '关注板块新闻 1 条：白酒',
          payload: {
            items: [{ news_id: 302, symbol: '白酒', name: '白酒', title: '白酒需求回暖', detail: '利多·中 需求回暖' }],
          },
        }),
        buildAlert({
          id: 12,
          kind: 'opportunity_digest',
          symbol: null,
          title: 'AI 发现的新机会 1 条：宁德时代',
          payload: { items: [{ news_id: 303, symbol: '300750.SZ', name: '宁德时代', title: '获大单', detail: '利多·强 订单超预期' }] },
        }),
        buildAlert({
          id: 11,
          kind: 'watch_news_digest',
          symbol: null,
          title: '自选股新闻 1 条：茅台',
          payload: { items: [{ news_id: 304, symbol: '600519.SH', name: '茅台', title: '提价' }] },
        }),
      ],
      degraded: false,
    });
    const wrapper = mountView();
    await flushPromises();

    const items = wrapper.findAll('[data-role="alert-item"]');
    expect(items[0].text()).toContain('海外重大');
    expect(items[0].find('.text-warning').exists()).toBe(true);
    expect(items[1].text()).toContain('关注板块');
    expect(items[2].text()).toContain('新机会');
    expect(items[3].text()).toContain('自选股新闻');
    expect(wrapper.text()).not.toContain('关注股新闻');

    const digestItems = wrapper.findAll('[data-role="alert-digest-item"]');
    expect(digestItems[0].text()).toBe('白酒（利多·中 需求回暖）：白酒需求回暖');
    expect(digestItems[1].text()).toBe('宁德时代（利多·强 订单超预期）：获大单');
    expect(digestItems[2].text()).toBe('茅台：提价');
    expect(digestItems[2].find('[data-role="alert-digest-detail"]').exists()).toBe(false);

    const targets = wrapper.findAllComponents(RouterLinkStub).map((link) => link.props('to'));
    expect(targets).toEqual(expect.arrayContaining(['/news/301', '/news/302', '/news/303', '/news/304']));
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
