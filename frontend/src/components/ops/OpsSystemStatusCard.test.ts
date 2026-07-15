import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsDatabase, OpsEventBus } from '../../types/api';
import OpsSystemStatusCard from './OpsSystemStatusCard.vue';

function buildEventBus(overrides: Partial<OpsEventBus> = {}): OpsEventBus {
  return {
    status: 'ok',
    backend: 'redis',
    redis_enabled: true,
    last_event_name: 'news.created',
    last_published_at: '2026-07-14T02:00:00Z',
    last_error: null,
    ...overrides,
  };
}

function buildDatabase(overrides: Partial<OpsDatabase> = {}): OpsDatabase {
  return {
    exists: true,
    size_bytes: 52_428_800,
    size_mb: 50,
    path: '/data/news.db',
    ...overrides,
  };
}

describe('OpsSystemStatusCard', () => {
  it('shows loading hints in both sections when eventBus and database are null', () => {
    const wrapper = mount(OpsSystemStatusCard, { props: { eventBus: null, database: null } });

    const emptyBlocks = wrapper.findAll('.ops-empty');
    expect(emptyBlocks).toHaveLength(2);
    expect(wrapper.find('[data-role="ops-event-bus"]').text()).toContain('加载中');
    expect(wrapper.find('[data-role="ops-database"]').text()).toContain('加载中');
  });

  it('renders event bus backend/redis/last event details and an ok pill', () => {
    const wrapper = mount(OpsSystemStatusCard, {
      props: { eventBus: buildEventBus(), database: buildDatabase() },
    });

    const busSection = wrapper.find('[data-role="ops-event-bus"]');
    expect(busSection.text()).toContain('redis');
    expect(busSection.text()).toContain('已启用');
    expect(busSection.text()).toContain('news.created');
    expect(busSection.find('.pill').classes()).toContain('success');
  });

  it('shows the warn pill and error line when event bus is degraded', () => {
    const wrapper = mount(OpsSystemStatusCard, {
      props: {
        eventBus: buildEventBus({ status: 'degraded', last_error: 'redis connection lost' }),
        database: buildDatabase(),
      },
    });

    const busSection = wrapper.find('[data-role="ops-event-bus"]');
    expect(busSection.find('.pill').classes()).toContain('ops-pill-warn');
    expect(busSection.text()).toContain('错误：redis connection lost');
  });

  it('renders database size, byte count and path', () => {
    const wrapper = mount(OpsSystemStatusCard, {
      props: { eventBus: buildEventBus(), database: buildDatabase() },
    });

    const dbSection = wrapper.find('[data-role="ops-database"]');
    expect(dbSection.text()).toContain('50.00 MB');
    expect(dbSection.text()).toContain('52,428,800');
    expect(dbSection.text()).toContain('/data/news.db');
  });
});
