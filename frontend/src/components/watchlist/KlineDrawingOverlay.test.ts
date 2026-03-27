import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KlineDrawingOverlay from './KlineDrawingOverlay.vue';

let resizeObserverCallback: ResizeObserverCallback | null = null;

beforeEach(() => {
  resizeObserverCallback = null;
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: ResizeObserverCallback) {
        resizeObserverCallback = callback;
      }
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
});

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

  it('renders crosshair labels and emits commit events for editable drawings', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
          { time: '2026-03-20', open: 551, high: 560, low: 545, close: 558.3, volume: 980 },
        ],
        drawings: [
          {
            id: 'trend-1',
            symbol: '0700.HK',
            toolType: 'trend_line',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
            anchors: [
              { time: '2026-03-18', price: 533.2 },
              { time: '2026-03-19', price: 550.5 },
            ],
            payload: {},
          },
        ],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: 'trend-1',
      },
      attachTo: document.body,
    });

    const overlay = wrapper.get('[data-role="kline-drawing-overlay"]');
    Object.defineProperty(overlay.element, 'clientWidth', { value: 300, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 120, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 300,
        height: 120,
        right: 300,
        bottom: 120,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;

    await overlay.trigger('mousemove', { clientX: 150, clientY: 20 });
    expect(wrapper.find('[data-role="crosshair-vertical"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="crosshair-time-label"]').text()).toContain('2026-03-19');
    expect(wrapper.find('[data-role="crosshair-price-label"]').text()).toContain('555.00');
    expect(wrapper.find('[data-role="drawing-anchor-handle-trend-1-0"]').exists()).toBe(true);

    await wrapper.get('[data-role="drawing-anchor-handle-trend-1-1"]').trigger('mousedown', { clientX: 150, clientY: 20 });
    await overlay.trigger('mousemove', { clientX: 299, clientY: 10 });
    await overlay.trigger('mouseup', { clientX: 299, clientY: 10 });
    expect(wrapper.emitted('drawingAnchorCommit')?.[0]?.[0]).toBe('trend-1');
    expect(wrapper.emitted('drawingAnchorCommit')?.[0]?.[1]).toEqual([
      { time: '2026-03-18', price: 533.2 },
      { time: '2026-03-20', price: 557.5 },
    ]);

    await wrapper.get('[data-role="drawing-body-trend-1"]').trigger('mousedown', { clientX: 80, clientY: 55 });
    await overlay.trigger('mousemove', { clientX: 220, clientY: 65 });
    await overlay.trigger('mouseup', { clientX: 220, clientY: 65 });
    expect(wrapper.emitted('drawingMoveCommit')?.[0]?.[0]).toBe('trend-1');
    expect(wrapper.emitted('drawingMoveCommit')?.[0]?.[1]).toEqual([
      { time: '2026-03-18', price: 530.7 },
      { time: '2026-03-19', price: 548 },
    ]);
  });

  it('does not drag locked drawings', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
        ],
        drawings: [
          {
            id: 'horizontal-1',
            symbol: '0700.HK',
            toolType: 'horizontal_line',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: true,
            visible: true,
            style: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
            anchors: [{ time: '2026-03-18', price: 540 }],
            payload: {},
          },
        ],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: 'horizontal-1',
      },
      attachTo: document.body,
    });

    const overlay = wrapper.get('[data-role="kline-drawing-overlay"]');
    Object.defineProperty(overlay.element, 'clientWidth', { value: 300, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 120, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 300,
        height: 120,
        right: 300,
        bottom: 120,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;

    await overlay.trigger('mousemove', { clientX: 40, clientY: 40 });
    await wrapper.get('[data-role="drawing-body-horizontal-1"]').trigger('mousedown', { clientX: 40, clientY: 40 });
    await overlay.trigger('mousemove', { clientX: 200, clientY: 80 });
    await overlay.trigger('mouseup', { clientX: 200, clientY: 80 });
    expect(wrapper.emitted('drawingMoveCommit')).toBeUndefined();
  });

  it('clears stale drag sessions on mouseleave and refreshes size from ResizeObserver', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
          { time: '2026-03-20', open: 551, high: 560, low: 545, close: 558.3, volume: 980 },
        ],
        drawings: [
          {
            id: 'trend-1',
            symbol: '0700.HK',
            toolType: 'trend_line',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
            anchors: [
              { time: '2026-03-18', price: 533.2 },
              { time: '2026-03-19', price: 550.5 },
            ],
            payload: {},
          },
        ],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: 'trend-1',
      },
      attachTo: document.body,
    });

    const overlay = wrapper.get('[data-role="kline-drawing-overlay"]');
    Object.defineProperty(overlay.element, 'clientWidth', { value: 300, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 120, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 300,
        height: 120,
        right: 300,
        bottom: 120,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;

    await overlay.trigger('mousemove', { clientX: 150, clientY: 20 });
    await wrapper.get('[data-role="drawing-body-trend-1"]').trigger('mousedown', { clientX: 80, clientY: 55 });
    await overlay.trigger('mouseleave');
    await overlay.trigger('mouseup', { clientX: 220, clientY: 65 });
    expect(wrapper.emitted('drawingMoveCommit')).toBeUndefined();

    Object.defineProperty(overlay.element, 'clientWidth', { value: 360, configurable: true });
    Object.defineProperty(overlay.element, 'clientHeight', { value: 140, configurable: true });
    overlay.element.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 360,
        height: 140,
        right: 360,
        bottom: 140,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      }) as DOMRect;
    resizeObserverCallback?.([], {} as ResizeObserver);
    await overlay.trigger('mousemove', { clientX: 180, clientY: 20 });
    expect(wrapper.find('[data-role="crosshair-vertical"]').attributes('x1')).toBe('180');
  });
});
