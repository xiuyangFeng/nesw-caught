import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsXSource } from '../../types/api';
import OpsXSourcesCard from './OpsXSourcesCard.vue';

function buildXSource(overrides: Partial<OpsXSource> = {}): OpsXSource {
  return {
    provider_name: 'twitterapi_io',
    consecutive_failures: 0,
    success_rate: 0.95,
    avg_latency_ms: 620,
    total_fetches: 500,
    total_failures: 10,
    last_success_at: '2026-07-14T02:30:00Z',
    last_failure_at: null,
    last_error: null,
    ...overrides,
  };
}

describe('OpsXSourcesCard', () => {
  it('shows the empty hint when there are no X sources', () => {
    const wrapper = mount(OpsXSourcesCard, { props: { xSources: [] } });

    expect(wrapper.find('[data-role="ops-x-source-row"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无 X 源记录');
  });

  it('renders provider name, success rate and latency per X source', () => {
    const wrapper = mount(OpsXSourcesCard, {
      props: { xSources: [buildXSource({ provider_name: 'twitterapi_io' })] },
    });

    const rows = wrapper.findAll('[data-role="ops-x-source-row"]');
    expect(rows).toHaveLength(1);
    expect(wrapper.text()).toContain('twitterapi_io');
    expect(wrapper.text()).toContain('95.0%');
    expect(wrapper.text()).toContain('620ms');
  });

  it('surfaces the last error line when a provider reports one', () => {
    const wrapper = mount(OpsXSourcesCard, {
      props: {
        xSources: [buildXSource({ provider_name: 'flaky_provider', last_error: 'rate limited', consecutive_failures: 8 })],
      },
    });

    expect(wrapper.text()).toContain('最近错误：rate limited');
    expect(wrapper.text()).toContain('连败 8');
  });
});
