import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { KlineIndicatorTemplate } from '../../types/api';
import KlineIndicatorWorkbench from './KlineIndicatorWorkbench.vue';

const templates: KlineIndicatorTemplate[] = [
  {
    id: 'preset-classic',
    name: '经典均线',
    source: 'preset',
    overlayIndicators: [
      { kind: 'MA', params: { periods: [5, 10, 20, 60] } },
      { kind: 'BOLL', params: { period: 20, stdDev: 2 } },
    ],
    subIndicator: 'VOL',
  },
  {
    id: 'custom-trend',
    name: '趋势跟随',
    source: 'custom',
    overlayIndicators: [{ kind: 'MA', params: { periods: [8, 21, 55] } }],
    subIndicator: 'MACD',
  },
];

describe('KlineIndicatorWorkbench', () => {
  it('renders a denser side cabinet with template summary, library, and control clusters', async () => {
    const wrapper = mount(KlineIndicatorWorkbench, {
      props: {
        templates,
        activeTemplateId: 'custom-trend',
        subIndicator: 'MACD',
      },
    });

    expect(wrapper.get('[data-role="kline-indicator-workbench"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="workbench-template-header"]').text()).toContain('趋势跟随');
    expect(wrapper.get('[data-role="active-template-summary"]').text()).toContain('MA8/21/55');
    expect(wrapper.get('[data-role="workbench-template-library"]').text()).toContain('经典均线');
    expect(wrapper.get('[data-role="workbench-action-row"]').text()).toContain('另存为模板');
    expect(wrapper.get('[data-role="workbench-subindicator-row"]').text()).toContain('MACD');

    await wrapper.get('[data-role="template-card-preset-classic"]').trigger('click');
    expect(wrapper.emitted('templateApply')?.[0]?.[0]).toBe('preset-classic');

    await wrapper.get('[data-role="template-save"]').trigger('click');
    expect(wrapper.emitted('templateSave')).toHaveLength(1);

    await wrapper.get('[data-role="template-delete"]').trigger('click');
    expect(wrapper.emitted('templateDelete')?.[0]?.[0]).toBe('custom-trend');

    await wrapper.get('[data-role="subindicator-RSI"]').trigger('click');
    expect(wrapper.emitted('subindicatorChange')?.[0]?.[0]).toBe('RSI');
  });
});
