import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, nextTick } from 'vue';
import { describe, expect, it, vi } from 'vitest';

vi.mock('vue-router', () => ({
  useRoute: () => ({ fullPath: '/x' }),
}));

import RouteErrorBoundary from './RouteErrorBoundary.vue';

const OkView = defineComponent({
  name: 'OkView',
  render() {
    return h('div', { 'data-role': 'ok-view' }, 'ok');
  },
});

describe('RouteErrorBoundary', () => {
  it('renders slot content normally when no error occurs', () => {
    const wrapper = mount(RouteErrorBoundary, {
      slots: { default: () => h(OkView) },
    });
    expect(wrapper.find('[data-role="ok-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(false);
  });

  it('contains an error thrown by a child view instead of letting it crash the app', async () => {
    const Boom = defineComponent({
      name: 'Boom',
      setup() {
        throw new Error('view exploded');
      },
      render() {
        return h('div');
      },
    });

    const wrapper = mount(RouteErrorBoundary, {
      slots: { default: () => h(Boom) },
    });
    await nextTick();

    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('view exploded');
  });

  it('recovers on retry without a full page refresh once the view stops throwing', async () => {
    let shouldThrow = true;
    const Flaky = defineComponent({
      name: 'Flaky',
      setup() {
        if (shouldThrow) {
          throw new Error('boom once');
        }
      },
      render() {
        return h('div', { 'data-role': 'flaky-ok' }, 'recovered');
      },
    });

    const wrapper = mount(RouteErrorBoundary, {
      slots: { default: () => h(Flaky) },
    });
    await nextTick();

    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(true);

    shouldThrow = false;
    await wrapper.find('[data-role="route-error-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="flaky-ok"]').exists()).toBe(true);
  });
});
