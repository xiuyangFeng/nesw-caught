import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DashboardHeader from './DashboardHeader.vue';

describe('DashboardHeader', () => {
  it('renders the secondary-overview headline and a tone-matched status badge', () => {
    const wrapper = mount(DashboardHeader, {
      props: {
        status: { label: '在线', detail: 'SSE live', tone: 'success' },
        stale: false,
      },
    });

    expect(wrapper.text()).toContain('Secondary Overview');
    expect(wrapper.text()).toContain('Dashboard');
    expect(wrapper.find('[data-role="dashboard-status-badge"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-status-badge"]').classes()).toContain(
      'dashboard-status-badge--success'
    );
    expect(wrapper.text()).toContain('在线');
    expect(wrapper.text()).toContain('SSE live');
  });

  it('forwards the stale flag to the stale badge', () => {
    const wrapper = mount(DashboardHeader, {
      props: {
        status: { label: '离线', detail: 'SSE off', tone: 'danger' },
        stale: true,
      },
    });

    expect(wrapper.find('[data-role="dashboard-status-badge"]').classes()).toContain(
      'dashboard-status-badge--danger'
    );
    expect(wrapper.text()).toContain('数据过期');
  });
});
