import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsAlert } from '../../types/api';
import OpsAlertsPanel from './OpsAlertsPanel.vue';

function buildAlert(overrides: Partial<OpsAlert> = {}): OpsAlert {
  return {
    code: 'worker_stalled',
    level: 'warning',
    message: 'Worker heartbeat 超时',
    subject: 'news_fetch_worker',
    ...overrides,
  };
}

describe('OpsAlertsPanel', () => {
  it('shows the all-nominal empty state when there are no alerts', () => {
    const wrapper = mount(OpsAlertsPanel, { props: { alerts: [] } });

    expect(wrapper.find('[data-role="ops-alert-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-alert"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('All systems nominal');
  });

  it('renders one alert row per alert with level, code, subject and message', () => {
    const wrapper = mount(OpsAlertsPanel, {
      props: {
        alerts: [
          buildAlert({ code: 'worker_stalled', level: 'warning', subject: 'news_fetch_worker' }),
          buildAlert({ code: 'db_size_high', level: 'critical', subject: 'database', message: '数据库体积超阈值' }),
        ],
      },
    });

    const rows = wrapper.findAll('[data-role="ops-alert"]');
    expect(rows).toHaveLength(2);
    expect(wrapper.find('[data-role="ops-alert-empty"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('worker_stalled');
    expect(wrapper.text()).toContain('news_fetch_worker');
    expect(wrapper.text()).toContain('db_size_high');
    expect(wrapper.text()).toContain('数据库体积超阈值');
    expect(rows[1]?.classes()).toContain('ops-alert--critical');
  });
});
