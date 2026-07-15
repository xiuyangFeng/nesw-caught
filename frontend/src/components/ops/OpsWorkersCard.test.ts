import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsWorker } from '../../types/api';
import OpsWorkersCard from './OpsWorkersCard.vue';

function buildWorker(overrides: Partial<OpsWorker> = {}): OpsWorker {
  return {
    name: 'news_fetch_worker',
    status: 'ok',
    heartbeat_age_seconds: 12,
    success_count: 100,
    failure_count: 0,
    cycle_count: 100,
    last_quotes_count: 0,
    last_success_at: '2026-07-14T03:00:00Z',
    last_failure_at: null,
    last_heartbeat_at: '2026-07-14T03:00:12Z',
    last_error: null,
    ...overrides,
  };
}

describe('OpsWorkersCard', () => {
  it('shows the empty hint and a zero count when there are no workers', () => {
    const wrapper = mount(OpsWorkersCard, { props: { workers: [] } });

    expect(wrapper.find('[data-role="ops-worker-row"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无 worker 运行记录');
    expect(wrapper.find('[data-role="ops-workers"] .ops-count').text()).toBe('0');
  });

  it('renders one row per worker with heartbeat age, counts and status pill', () => {
    const wrapper = mount(OpsWorkersCard, {
      props: {
        workers: [
          buildWorker({ name: 'news_fetch_worker', status: 'ok' }),
          buildWorker({ name: 'x_fetch_worker', status: 'degraded', heartbeat_age_seconds: 90 }),
        ],
      },
    });

    const rows = wrapper.findAll('[data-role="ops-worker-row"]');
    expect(rows).toHaveLength(2);
    expect(wrapper.text()).toContain('news_fetch_worker');
    expect(wrapper.text()).toContain('x_fetch_worker');
    expect(wrapper.text()).toContain('成功 100 / 失败 0');
    expect(wrapper.text()).toContain('2m 前');
    expect(rows[1]?.find('.pill').classes()).toContain('ops-pill-warn');
  });

  it('surfaces the last error line when a worker reports one', () => {
    const wrapper = mount(OpsWorkersCard, {
      props: {
        workers: [buildWorker({ status: 'error', last_error: 'connection refused' })],
      },
    });

    expect(wrapper.text()).toContain('最近错误：connection refused');
  });
});
