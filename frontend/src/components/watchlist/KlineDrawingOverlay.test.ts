import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import KlineDrawingOverlay from './KlineDrawingOverlay.vue';

describe('KlineDrawingOverlay', () => {
  it('emits hover-anchor-change in select mode and clears it on mouseleave', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
        ],
        drawings: [],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: null,
      },
      attachTo: document.body,
    });

    const overlay = wrapper.get('[data-role="kline-drawing-overlay"]');
    Object.defineProperty(overlay.element, 'clientWidth', { value: 200, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 100, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 200,
        height: 100,
        right: 200,
        bottom: 100,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;

    await overlay.trigger('mousemove', { clientX: 20, clientY: 30 });
    expect(wrapper.emitted('hoverAnchorChange')?.[0]?.[0]).toMatchObject({ time: '2026-03-18' });

    await overlay.trigger('mouseleave');
    expect(wrapper.emitted('hoverAnchorChange')?.[1]?.[0]).toBeNull();
  });

  it('keeps hover emission in drawing mode and emits null when disabled', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
        ],
        drawings: [],
        draftAnchors: [{ time: '2026-03-18', price: 533.2 }],
        activeTool: 'trend_line',
        selectedDrawingId: null,
      },
      attachTo: document.body,
    });

    const overlay = wrapper.get('[data-role="kline-drawing-overlay"]');
    Object.defineProperty(overlay.element, 'clientWidth', { value: 200, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 100, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 200,
        height: 100,
        right: 200,
        bottom: 100,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;

    await overlay.trigger('mousemove', { clientX: 180, clientY: 40 });
    expect(wrapper.emitted('hoverAnchorChange')?.[0]?.[0]).toMatchObject({ time: '2026-03-19' });
    expect(wrapper.emitted('draftUpdate')?.[0]?.[0]).toMatchObject({ time: '2026-03-19' });

    await wrapper.setProps({ disabled: true });
    await overlay.trigger('mousemove', { clientX: 180, clientY: 40 });
    expect(wrapper.emitted('hoverAnchorChange')?.[1]?.[0]).toBeNull();
  });
});
