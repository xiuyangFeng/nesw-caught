import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DashboardFilterBar from './DashboardFilterBar.vue';

const markets = [
  { label: '全部', value: null },
  { label: 'A股', value: 'cn' as const },
];

const sentiments = [
  { label: '全部', value: null },
  { label: '偏利好', value: 'positive' },
];

describe('DashboardFilterBar', () => {
  it('highlights the active market filter', () => {
    const wrapper = mount(DashboardFilterBar, {
      props: {
        markets,
        sentiments,
        selectedMarket: 'cn',
        selectedSentiment: null,
      },
    });

    const activeButton = wrapper.findAll('button').find((btn) => btn.text() === 'A股');
    expect(activeButton?.classes()).toContain('text-accent');
  });

  it('emits update events with the clicked filter value', async () => {
    const wrapper = mount(DashboardFilterBar, {
      props: {
        markets,
        sentiments,
        selectedMarket: null,
        selectedSentiment: null,
      },
    });

    const buttons = wrapper.findAll('button');
    await buttons.find((btn) => btn.text() === 'A股')!.trigger('click');
    expect(wrapper.emitted('update:selectedMarket')?.[0]).toEqual(['cn']);

    await buttons.find((btn) => btn.text() === '偏利好')!.trigger('click');
    expect(wrapper.emitted('update:selectedSentiment')?.[0]).toEqual(['positive']);
  });
});
