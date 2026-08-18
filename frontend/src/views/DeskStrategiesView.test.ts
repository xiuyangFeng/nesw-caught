import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskStrategiesView from './DeskStrategiesView.vue';

const { getQuantStrategies, previewQuantStrategy, createQuantStrategy } = vi.hoisted(() => ({
  getQuantStrategies: vi.fn(),
  previewQuantStrategy: vi.fn(),
  createQuantStrategy: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { getQuantStrategies, previewQuantStrategy, createQuantStrategy },
}));

describe('DeskStrategiesView', () => {
  beforeEach(() => {
    getQuantStrategies.mockResolvedValue({ data: [], degraded: false });
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
});
