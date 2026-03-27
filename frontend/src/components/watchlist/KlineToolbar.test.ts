import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import KlineToolbar from './KlineToolbar.vue';

describe('KlineToolbar', () => {
  it('renders a grouped terminal-style control strip and preserves control actions', async () => {
    const wrapper = mount(KlineToolbar, {
      props: {
        currentPeriod: '1W',
        activeTool: 'trend_line',
        drawingDisabled: false,
        collapsed: false,
        canUndo: true,
        canRedo: false,
      },
    });

    expect(wrapper.get('[data-role="kline-toolbar-shell"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="kline-toolbar-period-group"]').text()).toContain('日K');
    expect(wrapper.get('[data-role="kline-toolbar-action-group"]').text()).toContain('清空画线');
    expect(wrapper.get('[data-role="kline-toolbar-action-group"]').text()).toContain('撤销');
    expect(wrapper.get('[data-role="kline-toolbar-action-group"]').text()).toContain('重做');
    expect(wrapper.get('[data-role="kline-toolbar-tool-group"]').text()).toContain('趋势线');
    expect(wrapper.get('[data-role="period-chip-1W"]').attributes('data-active')).toBe('true');
    expect(wrapper.get('[data-role="tool-chip-trend_line"]').attributes('data-active')).toBe('true');

    await wrapper.get('[data-role="period-chip-1D"]').trigger('click');
    expect(wrapper.emitted('periodChange')?.[0]?.[0]).toBe('1D');

    await wrapper.get('[data-role="tool-chip-price_note"]').trigger('click');
    expect(wrapper.emitted('toolChange')?.[0]?.[0]).toBe('price_note');

    await wrapper.get('[data-role="clear-drawings"]').trigger('click');
    expect(wrapper.emitted('clearDrawings')).toHaveLength(1);

    expect(wrapper.get('[data-role="undo-action"]').attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-role="redo-action"]').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-role="undo-action"]').trigger('click');
    expect(wrapper.emitted('undo')).toHaveLength(1);

    await wrapper.get('[data-role="toggle-dashboard"]').trigger('click');
    expect(wrapper.emitted('toggleDashboard')).toHaveLength(1);
  });
});
