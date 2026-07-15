import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DashboardMoversColumn from './DashboardMoversColumn.vue';

const routerLinkStub = {
  props: ['to'],
  template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
};

function buildMover(overrides: Record<string, unknown> = {}) {
  return {
    symbol: 'NVDA',
    market: 'us',
    display_name: 'NVIDIA',
    abnormal_reason: 'price_spike',
    fetched_at: '2026-03-18T08:00:00Z',
    has_hot_alert: false,
    is_abnormal: true,
    ...overrides,
  };
}

describe('DashboardMoversColumn', () => {
  it('renders the signal count, top reason, and a 2-item preview list', () => {
    const wrapper = mount(DashboardMoversColumn, {
      props: {
        movers: [
          buildMover(),
          buildMover({ symbol: '0700.HK', market: 'hk', display_name: 'Tencent', abnormal_reason: 'price_move' }),
          buildMover({ symbol: '9988.HK', market: 'hk', display_name: 'Alibaba', abnormal_reason: 'price_move' }),
        ] as any,
        loading: false,
      },
      global: { stubs: { RouterLink: routerLinkStub } },
    });

    expect(wrapper.text()).toContain('3 只异动');
    expect(wrapper.findAll('[data-role="movement-preview-item"]')).toHaveLength(2);
    expect(wrapper.text()).toContain('价格异动');
  });

  it('shows the empty state copy when there are no movers', () => {
    const wrapper = mount(DashboardMoversColumn, {
      props: { movers: [], loading: false },
      global: { stubs: { RouterLink: routerLinkStub } },
    });

    expect(wrapper.text()).toContain('暂无异动');
  });
});
