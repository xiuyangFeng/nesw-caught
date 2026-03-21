import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import HeroMetrics from './HeroMetrics.vue';

describe('HeroMetrics', () => {
  it('renders terminal metric labels and tone hooks', () => {
    const wrapper = mount(HeroMetrics, {
      props: {
        metrics: [
          {
            label: 'News Count',
            value: '24',
            note: 'Current load',
            tone: 'default',
          },
        ],
      },
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
          },
        },
      },
    });

    expect(wrapper.find('[data-role="metric-label"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="metric-value"]').text()).toBe('24');
    expect(wrapper.find('[data-role="metric-note"]').text()).toBe('Current load');
  });

  it('exposes stable card markers for each metric item', () => {
    const wrapper = mount(HeroMetrics, {
      props: {
        metrics: [
          {
            label: 'Positive',
            value: '12',
            note: 'Positive names',
            tone: 'positive',
          },
          {
            label: 'Negative',
            value: '4',
            note: 'Risk names',
            tone: 'negative',
          },
        ],
      },
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
          },
        },
      },
    });

    expect(wrapper.find('[data-role="hero-grid"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="metric-card"]')).toHaveLength(2);
    expect(wrapper.findAll('[data-role="metric-card"]')[1]?.attributes('data-tone')).toBe('negative');
  });

  it('renders route-backed metrics as clickable cards and leaves static metrics non-interactive', () => {
    const wrapper = mount(HeroMetrics, {
      props: {
        metrics: [
          {
            label: 'Positive',
            value: '12',
            note: 'Open positive flow',
            tone: 'positive',
            to: '/news/sentiment/positive',
          },
          {
            label: 'Count',
            value: '24',
            note: 'Still static',
            tone: 'default',
          },
        ],
      },
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a data-role="metric-link" :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
          },
        },
      },
    });

    expect(wrapper.find('[data-role="metric-link"]').attributes('href')).toBe('/news/sentiment/positive');
    expect(wrapper.findAll('[data-role="metric-card"]')).toHaveLength(1);
  });
});
