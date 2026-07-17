import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsSource } from '../../types/api';
import OpsSourcesCard from './OpsSourcesCard.vue';

function buildSource(overrides: Partial<OpsSource> = {}): OpsSource {
  return {
    source_name: 'Reuters HK',
    market: 'hk',
    source_type: 'rss',
    consecutive_failures: 0,
    is_disabled: false,
    success_rate: 0.98,
    avg_latency_ms: 412,
    total_failures: 2,
    total_fetches: 200,
    last_success_at: '2026-07-14T02:00:00Z',
    last_failure_at: null,
    last_status: 'ok',
    last_error: null,
    last_http_status: 200,
    last_fetched_count: 8,
    last_inserted_count: 2,
    consecutive_empty_batches: 0,
    ...overrides,
  };
}

describe('OpsSourcesCard', () => {
  it('shows the empty hint when there are no sources', () => {
    const wrapper = mount(OpsSourcesCard, { props: { sources: [] } });

    expect(wrapper.find('[data-role="ops-source-row"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无新闻源记录');
  });

  it('renders success rate, consecutive failures and latency per source', () => {
    const wrapper = mount(OpsSourcesCard, {
      props: {
        sources: [
          buildSource({ source_name: 'Reuters HK' }),
          buildSource({ source_name: 'Broken Wire', consecutive_failures: 6, success_rate: 0.4, avg_latency_ms: null }),
        ],
      },
    });

    const rows = wrapper.findAll('[data-role="ops-source-row"]');
    expect(rows).toHaveLength(2);
    expect(wrapper.text()).toContain('98.0%');
    expect(wrapper.text()).toContain('412ms');
    expect(wrapper.text()).toContain('连败 6');
  });

  it('marks a disabled source with the disabled pill', () => {
    const wrapper = mount(OpsSourcesCard, {
      props: { sources: [buildSource({ source_name: 'Disabled Wire', is_disabled: true })] },
    });

    expect(wrapper.text()).toContain('disabled');
    expect(wrapper.find('.pill.ops-pill-crit').exists()).toBe(true);
  });

  it('renders last_status, http, counts, empty streak and last_error', () => {
    const wrapper = mount(OpsSourcesCard, {
      props: {
        sources: [
          buildSource({
            source_name: 'Empty Wire',
            last_status: 'empty',
            last_http_status: 200,
            last_fetched_count: 0,
            last_inserted_count: 0,
            consecutive_empty_batches: 3,
            last_error: 'parsed 0 items',
          }),
        ],
      },
    });

    const text = wrapper.text();
    expect(text).toContain('empty');
    expect(text).toContain('HTTP 200');
    expect(text).toContain('解析 0');
    expect(text).toContain('入库 0');
    expect(text).toContain('空批 3');
    expect(text).toContain('parsed 0 items');
  });
});
