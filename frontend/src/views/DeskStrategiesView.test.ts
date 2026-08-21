import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskStrategiesView from './DeskStrategiesView.vue';

const { getQuantStrategies, getQuantFactors, previewQuantStrategy, createQuantStrategy, updateQuantStrategy, deleteQuantStrategy } =
  vi.hoisted(() => ({
    getQuantStrategies: vi.fn(),
    getQuantFactors: vi.fn(),
    previewQuantStrategy: vi.fn(),
    createQuantStrategy: vi.fn(),
    updateQuantStrategy: vi.fn(),
    deleteQuantStrategy: vi.fn(),
  }));

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock('../api/client', () => ({
  apiClient: { getQuantStrategies, getQuantFactors, previewQuantStrategy, createQuantStrategy, updateQuantStrategy, deleteQuantStrategy },
}));

vi.mock('vue-router', () => ({
  useRouter: () => routerMock,
}));

const registeredFactors = [
  { key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' },
  { key: 'news_novelty', sleeve: 'event_catalyst', horizon: '5d' },
  { key: 'gap_unfilled', sleeve: 'fundamental_revalue', horizon: '60d' },
];

const savedStrategy = {
  id: 7,
  name: '主力流入趋势',
  dsl: {
    sleeve: 'trend_flow',
    horizon: '20d',
    logic: 'and',
    conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
  },
  is_active: false,
  exploratory: true,
  errors: [],
};

describe('DeskStrategiesView', () => {
  beforeEach(() => {
    getQuantStrategies.mockReset();
    getQuantFactors.mockReset();
    previewQuantStrategy.mockReset();
    createQuantStrategy.mockReset();
    updateQuantStrategy.mockReset();
    deleteQuantStrategy.mockReset();
    getQuantStrategies.mockResolvedValue({ data: [], degraded: false });
    getQuantFactors.mockResolvedValue({ data: registeredFactors, degraded: false });
    previewQuantStrategy.mockResolvedValue({ data: { errors: [], hit: true }, degraded: false });
    createQuantStrategy.mockResolvedValue({
      data: { id: 1, name: '主力流入趋势', dsl: {}, is_active: false, exploratory: true, errors: [] },
      degraded: false,
    });
  });

  it('previews the DSL built by the structured builder', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-strategies-view"]').exists()).toBe(true);
    await wrapper.get('[data-role="desk-strategy-preview"]').trigger('click');
    await flushPromises();
    expect(previewQuantStrategy).toHaveBeenCalled();
    expect(wrapper.get('[data-role="desk-strategy-preview-result"]').text()).toContain('校验通过');
    const payload = previewQuantStrategy.mock.calls[0][0];
    expect(payload.dsl.sleeve).toBe('trend_flow');
    expect(payload.dsl.conditions[0].factor).toBe('main_inflow_1d');
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

  it('saves the strategy assembled by the builder', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-save"]').trigger('click');
    await flushPromises();

    expect(createQuantStrategy).toHaveBeenCalled();
    const payload = createQuantStrategy.mock.calls[0][0];
    expect(payload.dsl.conditions).toHaveLength(1);
    expect(payload.dsl.conditions[0]).toEqual({ factor: 'main_inflow_1d', op: '>', value: 50_000_000 });
  });

  it('shows a seed-pending empty state when no strategies are saved yet', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    expect(wrapper.get('[data-role="desk-strategies-empty"]').text()).toContain('默认探索性策略将在后端完成种子后自动出现');
  });

  it('edits conditions through the builder instead of raw JSON', async () => {
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    // 构建器默认展示一行条件：因子下拉 + 运算符 + 阈值输入，而不是 JSON textarea
    expect(wrapper.find('[data-role="strategy-builder-root"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(1);

    await wrapper.get('[data-role="strategy-builder-add"]').trigger('click');
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(2);

    const valueInput = wrapper.get('[data-role="strategy-builder-value"]').element as HTMLInputElement;
    await wrapper.get('[data-role="strategy-builder-value"]').setValue('12345');
    expect(Number(valueInput.value)).toBe(12345);

    await wrapper.get('[data-role="desk-strategy-save"]').trigger('click');
    await flushPromises();
    const payload = createQuantStrategy.mock.calls[0][0];
    expect(payload.dsl.conditions).toHaveLength(2);
  });

  it('edits a saved strategy via PATCH and cancels back', async () => {
    getQuantStrategies.mockResolvedValue({ data: [savedStrategy], degraded: false });
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-edit"]').trigger('click');
    expect(wrapper.get('[data-role="desk-strategy-editing"]').text()).toContain('编辑模式');
    expect((wrapper.get('[data-role="desk-strategy-name"]').element as HTMLInputElement).value).toBe('主力流入趋势');

    await wrapper.get('[data-role="desk-strategy-name"]').setValue('改名的策略');
    await wrapper.get('[data-role="desk-strategy-save"]').trigger('click');
    await flushPromises();

    expect(updateQuantStrategy).toHaveBeenCalledWith(7, { name: '改名的策略', dsl: expect.any(Object) });
    expect(createQuantStrategy).not.toHaveBeenCalled();
    // 保存后退出编辑模式
    expect(wrapper.find('[data-role="desk-strategy-editing"]').exists()).toBe(false);
  });

  it('deletes a strategy after confirmation', async () => {
    getQuantStrategies.mockResolvedValue({ data: [savedStrategy], degraded: false });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-delete"]').trigger('click');
    await flushPromises();
    expect(deleteQuantStrategy).toHaveBeenCalledWith(7);
    confirmSpy.mockRestore();
  });

  it('skips deletion when confirmation is declined', async () => {
    getQuantStrategies.mockResolvedValue({ data: [savedStrategy], degraded: false });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-delete"]').trigger('click');
    await flushPromises();
    expect(deleteQuantStrategy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('navigates to the backtest lab with the strategy preset', async () => {
    getQuantStrategies.mockResolvedValue({ data: [savedStrategy], degraded: false });
    const wrapper = mount(DeskStrategiesView);
    await flushPromises();

    await wrapper.get('[data-role="desk-strategy-backtest"]').trigger('click');
    await flushPromises();
    expect(routerMock.push).toHaveBeenCalledWith({ path: '/desk/backtest', query: { strategy: '7' } });
  });
});
