import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { describe, expect, it } from 'vitest';

import RouteErrorBoundary from './RouteErrorBoundary.vue';

// End-to-end proof of the reported bug's fix, using the REAL vue-router:
// navigating to a module whose view throws must not freeze the app, and
// switching to another module must recover WITHOUT a full page refresh.

const GoodView = defineComponent({
  name: 'GoodView',
  render() {
    return h('div', { 'data-role': 'good-view' }, 'good module');
  },
});

const BoomView = defineComponent({
  name: 'BoomView',
  setup() {
    throw new Error('module blew up during setup');
  },
  render() {
    return h('div');
  },
});

const Shell = defineComponent({
  name: 'Shell',
  components: { RouteErrorBoundary, RouterView },
  template: '<RouteErrorBoundary><RouterView /></RouteErrorBoundary>',
});

describe('RouteErrorBoundary (integration with real vue-router)', () => {
  it('contains a throwing module then recovers when switching modules, no refresh', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', redirect: '/good' },
        { path: '/good', component: GoodView },
        { path: '/boom', component: BoomView },
      ],
    });

    await router.push('/good');
    await router.isReady();

    const wrapper = mount(Shell, { global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.find('[data-role="good-view"]').exists()).toBe(true);

    // Navigate to the broken module: the boundary must catch, not crash.
    await router.push('/boom');
    await flushPromises();
    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('module blew up');

    // Switch to another module: recovers automatically, no manual refresh.
    await router.push('/good');
    await flushPromises();
    expect(wrapper.find('[data-role="route-error-boundary"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="good-view"]').exists()).toBe(true);
  });
});
