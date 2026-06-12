import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsRuntimeSource } from '../../types/api';
import SourceHealthGrid from './SourceHealthGrid.vue';

function buildSource(overrides: Partial<NewsRuntimeSource> = {}): NewsRuntimeSource {
  return {
    source_name: 'Example Wire',
    market: 'us',
    tier: 'primary',
    status: 'ok',
    last_attempt_at: '2026-06-12T03:00:00Z',
    last_success_at: '2026-06-12T03:00:00Z',
    consecutive_failures: 0,
    avg_fetch_latency_ms: 412.4,
    latest_news_published_at: '2026-06-12T02:58:00Z',
    latest_news_fetched_at: '2026-06-12T03:00:00Z',
    last_error: null,
    ...overrides,
  };
}

describe('SourceHealthGrid', () => {
  it('renders one row per source with status and latency', () => {
    const wrapper = mount(SourceHealthGrid, {
      props: {
        sources: [
          buildSource({ source_name: 'Alpha Feed' }),
          buildSource({ source_name: 'Beta Feed', status: 'offline', consecutive_failures: 5, avg_fetch_latency_ms: null }),
        ],
      },
    });

    const rows = wrapper.findAll('[data-role="source-health-row"]');
    expect(rows).toHaveLength(2);
    expect(wrapper.text()).toContain('412ms');
    expect(wrapper.text()).toContain('连续失败 5');
    expect(wrapper.text()).toContain('OFFLINE');
  });

  it('sorts unhealthy sources before healthy ones', () => {
    const wrapper = mount(SourceHealthGrid, {
      props: {
        sources: [
          buildSource({ source_name: 'Healthy', status: 'ok' }),
          buildSource({ source_name: 'Broken', status: 'offline' }),
          buildSource({ source_name: 'Slow', status: 'delayed' }),
        ],
      },
    });

    const statuses = wrapper
      .findAll('[data-role="source-health-row"]')
      .map((row) => row.attributes('data-status'));
    expect(statuses).toEqual(['offline', 'delayed', 'ok']);
  });

  it('shows summary counts and an empty hint when no sources exist', () => {
    const wrapper = mount(SourceHealthGrid, {
      props: { sources: [] },
    });

    expect(wrapper.find('[data-role="source-health-summary"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('暂无来源健康数据');
  });
});
