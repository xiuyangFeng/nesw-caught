import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import StrategyBuilder from './StrategyBuilder.vue';

const factors = [
  { key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' },
  { key: 'news_novelty', sleeve: 'event_catalyst', horizon: '5d' },
];

const initialDsl = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
};

function mountBuilder(dsl: Record<string, unknown> = { ...initialDsl }) {
  const updates: Record<string, unknown>[] = [];
  const wrapper = mount(StrategyBuilder, {
    props: { modelValue: dsl, factors },
    emits: { 'update:modelValue': (value: Record<string, unknown>) => updates.push(value) },
  });
  return { wrapper, updates };
}

describe('StrategyBuilder', () => {
  it('parses the incoming DSL into structured rows and emits it back unchanged', async () => {
    const { wrapper, updates } = mountBuilder();
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(1);

    // 任意一次行内编辑都会触发一次与构建器状态一致的 emit
    await wrapper.get('[data-role="strategy-builder-value"]').setValue('123');
    expect(updates.length).toBeGreaterThan(0);
    const emitted = updates[updates.length - 1];
    expect(emitted.sleeve).toBe('trend_flow');
    expect(emitted.horizon).toBe('20d');
    expect(emitted.logic).toBe('and');
    expect(emitted.conditions).toEqual([{ factor: 'main_inflow_1d', op: '>', value: 123 }]);
  });

  it('adds and removes condition rows', async () => {
    const { wrapper } = mountBuilder();
    await wrapper.get('[data-role="strategy-builder-add"]').trigger('click');
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(2);

    await wrapper.findAll('[data-role="strategy-builder-remove"]')[1].trigger('click');
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(1);

    // 最后一行不可删除：至少保留一个条件
    await wrapper.get('[data-role="strategy-builder-remove"]').trigger('click');
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(1);
  });

  it('switches factor and operator from the registry-driven selects', async () => {
    const { wrapper, updates } = mountBuilder();
    await wrapper.get('[data-role="strategy-builder-factor"]').setValue('news_novelty');
    await wrapper.get('[data-role="strategy-builder-op"]').setValue('<=');
    const emitted = updates[updates.length - 1] as { conditions: { factor: string; op: string }[] };
    expect(emitted.conditions[0].factor).toBe('news_novelty');
    expect(emitted.conditions[0].op).toBe('<=');
  });

  it('exposes an advanced JSON mode that applies valid edits and rejects invalid JSON', async () => {
    const { wrapper, updates } = mountBuilder();
    await wrapper.get('[data-role="strategy-builder-advanced-toggle"]').trigger('click');

    const textarea = wrapper.get('[data-role="strategy-builder-advanced-text"]').element as HTMLTextAreaElement;
    expect(textarea.value).toContain('"sleeve": "trend_flow"');

    const edited = { ...initialDsl, logic: 'or' };
    await wrapper.get('[data-role="strategy-builder-advanced-text"]').setValue(JSON.stringify(edited, null, 2));
    await wrapper.get('[data-role="strategy-builder-advanced-apply"]').trigger('click');
    expect(wrapper.find('[data-role="strategy-builder-advanced-error"]').exists()).toBe(false);
    expect(updates[updates.length - 1]).toEqual(edited);

    await wrapper.get('[data-role="strategy-builder-advanced-text"]').setValue('{ not json');
    await wrapper.get('[data-role="strategy-builder-advanced-apply"]').trigger('click');
    expect(wrapper.get('[data-role="strategy-builder-advanced-error"]').text()).toContain('JSON 无法解析');
  });

  it('flags nested DSL that the flat builder cannot express', () => {
    const nestedDsl = {
      sleeve: 'trend_flow',
      horizon: '20d',
      logic: 'and',
      conditions: [
        { factor: 'main_inflow_1d', op: '>', value: 1 },
        { logic: 'or', conditions: [{ factor: 'news_novelty', op: '>', value: 0.5 }] },
      ],
    };
    const { wrapper } = mountBuilder(nestedDsl);
    expect(wrapper.find('[data-role="strategy-builder-nested-note"]').exists()).toBe(true);
  });
});
