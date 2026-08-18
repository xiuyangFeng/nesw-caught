import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskStrategiesView from './DeskStrategiesView.vue';

const { getQuantStrategies, getQuantFactors, previewQuantStrategy, createQuantStrategy } = vi.hoisted(() => ({
  getQuantStrategies: vi.fn(),
  getQuantFactors: vi.fn(),
  previewQuantStrategy: vi.fn(),
  createQuantStrategy: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { getQuantStrategies, getQuantFactors, previewQuantStrategy, createQuantStrategy },
}));

const registeredFactors = [
  { key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' },
  { key: 'news_novelty', sleeve: 'event_catalyst', horizon: '5d' },
  { key: 'gap_unfilled', sleeve: 'fundamental_revalue', horizon: '60d' },
];

describe('DeskStrategiesView', () => {
  beforeEach(() => {
    getQuantStrategies.mockResolvedValue({ data: [], degraded: false });
    getQuantFactors.mockResolvedValue({ data: registeredFactors, degraded: false });
    previewQuantStrategy.mockResolvedValue({ data: { errors: [], hit: true }, degraded: false });
    createQuantStrategy.mockResolvedValue({
      data: { id: 1, name: '主力流入趋势', dsl: {}, is_active: false, exploratory: true, errors: [] },
      degraded: false,
    });
  });

  it('previews a registered-factor DSL', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-strategies-view"]').exists()).toBe(true);
    await wrapper.get('[data-role="desk-strategy-preview"]').trigger('click');
    await flushPromises();
    expect(previewQuantStrategy).toHaveBeenCalled();
    expect(wrapper.get('[data-role="desk-strategy-preview-result"]').text()).toContain('合成特征命中 是');
  });

  it('renders the factor registry table fetched from the backend, with a mock fallback available', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    expect(getQuantFactors).toHaveBeenCalled();
    const registry = wrapper.get('[data-role="desk-factor-registry"]');
    expect(registry.text()).toContain('main_inflow_1d');
    expect(registry.text()).toContain('趋势/资金');
    expect(registry.text()).toContain('news_novelty');
    expect(registry.text()).toContain('gap_unfilled');
    expect(wrapper.findAll('[data-role="desk-factor-row"]')).toHaveLength(3);
  });

  it('fills the DSL editor with a template referencing a registered factor', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-fill-example"]').trigger('click');
    await flushPromises();

    const dsl = JSON.parse((wrapper.get('[data-role="desk-strategy-dsl"]').element as HTMLTextAreaElement).value);
    expect(dsl.conditions[0].factor).toBe(registeredFactors[0].key);
    expect(dsl.sleeve).toBe(registeredFactors[0].sleeve);
    expect((wrapper.get('[data-role="desk-strategy-name"]').element as HTMLInputElement).value).toContain(
      registeredFactors[0].key,
    );
  });

  it('shows a seed-pending empty state when no strategies are saved yet', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    expect(wrapper.get('[data-role="desk-strategy-empty"]').text()).toContain('默认探索性策略将在后端完成种子后自动出现');
  });
});
