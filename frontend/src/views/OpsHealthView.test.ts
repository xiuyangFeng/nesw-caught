import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OpsHealth } from '../types/api';

function buildHealth(overrides: Partial<OpsHealth> = {}): OpsHealth {
  return {
    generated_at: '2026-07-14T03:00:00Z',
    overall_status: 'ok',
    alerts: [],
    workers: [
      {
        name: 'news_fetch_worker',
        status: 'ok',
        heartbeat_age_seconds: 10,
        success_count: 50,
        failure_count: 0,
        cycle_count: 50,
        last_quotes_count: 0,
        last_success_at: '2026-07-14T02:59:00Z',
        last_failure_at: null,
        last_heartbeat_at: '2026-07-14T02:59:50Z',
        last_error: null,
      },
    ],
    sources: [
      {
        source_name: 'Reuters HK',
        market: 'hk',
        source_type: 'rss',
        consecutive_failures: 0,
        is_disabled: false,
        success_rate: 0.99,
        avg_latency_ms: 300,
        total_failures: 1,
        total_fetches: 100,
        last_success_at: '2026-07-14T02:58:00Z',
        last_failure_at: null,
      },
    ],
    x_sources: [
      {
        provider_name: 'twitterapi_io',
        consecutive_failures: 0,
        success_rate: 0.9,
        avg_latency_ms: 500,
        total_fetches: 100,
        total_failures: 5,
        last_success_at: '2026-07-14T02:57:00Z',
        last_failure_at: null,
        last_error: null,
      },
    ],
    llm_usage: {
      window_hours: 24,
      call_count: 12,
      total_tokens: 5000,
      prompt_tokens: 4000,
      completion_tokens: 1000,
      models: [{ model_name: 'gpt-4o-mini', call_count: 12, total_tokens: 5000, prompt_tokens: 4000, completion_tokens: 1000 }],
    },
    event_bus: {
      status: 'ok',
      backend: 'redis',
      redis_enabled: true,
      last_event_name: 'news.created',
      last_published_at: '2026-07-14T02:59:59Z',
      last_error: null,
    },
    database: {
      exists: true,
      size_bytes: 1_048_576,
      size_mb: 1,
      path: '/data/news.db',
    },
    ...overrides,
  };
}

const getOpsHealth = vi.fn();

vi.mock('../api/client', () => ({
  apiClient: {
    getOpsHealth: (...args: unknown[]) => getOpsHealth(...args),
  },
}));

import OpsHealthView from './OpsHealthView.vue';

describe('OpsHealthView', () => {
  beforeEach(() => {
    getOpsHealth.mockReset();
    getOpsHealth.mockResolvedValue({ data: buildHealth(), degraded: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads health on mount and renders the NOMINAL badge plus child sections', async () => {
    const wrapper = mount(OpsHealthView);
    await flushPromises();

    expect(getOpsHealth).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-role="ops-health-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-overall-badge"]').text()).toContain('NOMINAL');
    expect(wrapper.find('[data-role="ops-workers"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-llm"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-sources"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-x-sources"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-event-bus"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="ops-database"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('news_fetch_worker');
    expect(wrapper.text()).toContain('Reuters HK');
    expect(wrapper.text()).toContain('twitterapi_io');
    expect(wrapper.find('[data-role="ops-alert-empty"]').exists()).toBe(true);
  });

  it('renders gracefully with all-empty child sections before the first response resolves', () => {
    getOpsHealth.mockImplementation(() => new Promise(() => {}));
    const wrapper = mount(OpsHealthView);

    expect(wrapper.find('[data-role="ops-health-view"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('暂无 worker 运行记录');
    expect(wrapper.text()).toContain('暂无新闻源记录');
    expect(wrapper.text()).toContain('暂无 X 源记录');
    expect(wrapper.find('[data-role="ops-event-bus"]').text()).toContain('加载中');
    expect(wrapper.find('[data-role="ops-database"]').text()).toContain('加载中');
  });

  it('shows the WARNING badge with a warning count when alerts contain warnings', async () => {
    getOpsHealth.mockResolvedValue({
      data: buildHealth({
        overall_status: 'warning',
        alerts: [{ code: 'source_slow', level: 'warning', message: '时延偏高', subject: 'Reuters HK' }],
      }),
      degraded: false,
    });

    const wrapper = mount(OpsHealthView);
    await flushPromises();

    expect(wrapper.find('[data-role="ops-overall-badge"]').text()).toContain('WARNING');
    expect(wrapper.find('[data-role="ops-overall-badge"]').text()).toContain('1 项告警');
    expect(wrapper.findAll('[data-role="ops-alert"]')).toHaveLength(1);
  });

  it('shows the CRITICAL badge with a critical count when alerts contain criticals', async () => {
    getOpsHealth.mockResolvedValue({
      data: buildHealth({
        overall_status: 'critical',
        alerts: [{ code: 'db_size_high', level: 'critical', message: '体积超限', subject: 'database' }],
      }),
      degraded: false,
    });

    const wrapper = mount(OpsHealthView);
    await flushPromises();

    expect(wrapper.find('[data-role="ops-overall-badge"]').text()).toContain('CRITICAL');
    expect(wrapper.find('[data-role="ops-overall-badge"]').text()).toContain('1 项严重');
  });

  it('shows an inline error message and keeps the view usable when loading fails', async () => {
    getOpsHealth.mockRejectedValue(new Error('network down'));

    const wrapper = mount(OpsHealthView);
    await flushPromises();

    expect(wrapper.find('[data-role="ops-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('健康看板加载失败，请检查后端服务');
  });

  it('re-fetches health when the refresh button is clicked', async () => {
    const wrapper = mount(OpsHealthView);
    await flushPromises();
    expect(getOpsHealth).toHaveBeenCalledTimes(1);

    await wrapper.get('[data-role="ops-refresh"]').trigger('click');
    await flushPromises();

    expect(getOpsHealth).toHaveBeenCalledTimes(2);
  });

  it('polls every 15s while mounted and stops polling after unmount', async () => {
    vi.useFakeTimers();
    const wrapper = mount(OpsHealthView);
    await vi.advanceTimersByTimeAsync(0);
    expect(getOpsHealth).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(15_000);
    expect(getOpsHealth).toHaveBeenCalledTimes(2);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getOpsHealth).toHaveBeenCalledTimes(2);
  });
});
