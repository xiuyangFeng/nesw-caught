import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KlineDrawingOverlay from './KlineDrawingOverlay.vue';

let resizeObserverCallback: ResizeObserverCallback | null = null;

function dispatchTouchEvent(
  target: Element,
  type: 'touchstart' | 'touchmove' | 'touchend' | 'touchcancel',
  options:
    | { clientX: number; clientY: number }
    | {
        touches: Array<{ clientX: number; clientY: number }>;
        changedTouches?: Array<{ clientX: number; clientY: number }>;
      },
) {
  const inputTouches = 'touches' in options ? options.touches : [options];
  const inputChangedTouches = 'changedTouches' in options ? (options.changedTouches ?? options.touches) : [options];
  const buildTouchPoint = (touch: { clientX: number; clientY: number }) => ({
    clientX: touch.clientX,
    clientY: touch.clientY,
    pageX: touch.clientX,
    pageY: touch.clientY,
    screenX: touch.clientX,
    screenY: touch.clientY,
  });
  const touches = inputTouches.map(buildTouchPoint);
  const changedTouches = inputChangedTouches.map(buildTouchPoint);
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    touches: {
      value: type === 'touchend' || type === 'touchcancel' ? [] : touches,
      configurable: true,
    },
    changedTouches: {
      value: changedTouches,
      configurable: true,
    },
  });
  target.dispatchEvent(event);
  return event;
}

beforeEach(() => {
  resizeObserverCallback = null;
  Object.defineProperty(document, 'elementFromPoint', {
    value: vi.fn(() => null),
    configurable: true,
    writable: true,
  });
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
        chartProjector: {
          getXForTime: (time: string) => (time === '2026-03-19' ? 170 : null),
          getYForPrice: (price: number) => (price === 555 ? 18 : null),
          getTimeLabel: () => '03-19 10:30',
          getPriceLabel: () => '555.55',
        },
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
    expect(wrapper.find('[data-role="crosshair-time-label"]').text()).toContain('03-19 10:30');
    expect(wrapper.find('[data-role="crosshair-price-label"]').text()).toContain('555.55');
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

  it('supports fib editing and price-note label commits', async () => {
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
            id: 'fib-1',
            symbol: '0700.HK',
            toolType: 'fibonacci_retracement',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#c084fc', lineWidth: 1, lineStyle: 'solid', fillOpacity: 0.12 },
            anchors: [
              { time: '2026-03-18', price: 560 },
              { time: '2026-03-19', price: 530 },
            ],
            payload: {},
          },
          {
            id: 'note-1',
            symbol: '0700.HK',
            toolType: 'price_note',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#fb7185', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0 },
            anchors: [{ time: '2026-03-19', price: 545 }],
            payload: { text: '观察位' },
          },
        ],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: 'fib-1',
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
    expect(wrapper.find('[data-role="drawing-anchor-handle-fib-1-0"]').exists()).toBe(true);

    await wrapper.get('[data-role="drawing-body-fib-1"]').trigger('mousedown', { clientX: 80, clientY: 55 });
    await overlay.trigger('mouseup', { clientX: 220, clientY: 65 });
    expect(wrapper.emitted('drawingMoveCommit')?.[0]?.[0]).toBe('fib-1');

    await wrapper.setProps({ selectedDrawingId: 'note-1' });
    expect(wrapper.find('[data-role="drawing-anchor-handle-note-1-0"]').exists()).toBe(true);

    await wrapper.get('[data-role="drawing-body-note-1"]').trigger('mousedown', { clientX: 150, clientY: 60 });
    await overlay.trigger('mouseup', { clientX: 280, clientY: 70 });
    expect(wrapper.emitted('drawingMoveCommit')?.[1]?.[0]).toBe('note-1');

    await wrapper.get('[data-role="price-note-label-note-1"]').trigger('dblclick');
    expect(wrapper.emitted('labelEditingChange')?.[0]).toEqual([true]);
    const input = wrapper.get('[data-role="price-note-editor-input"]');
    await input.setValue('突破确认');
    await input.trigger('keydown.enter');
    expect(wrapper.emitted('drawingLabelCommit')?.[0]).toEqual(['note-1', '突破确认']);
    expect(wrapper.emitted('labelEditingChange')?.[1]).toEqual([false]);
    expect(wrapper.emitted('labelEditingChange')).toHaveLength(2);
  });

  it('emits label editing state changes on escape cancel and blur', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
        ],
        drawings: [
          {
            id: 'note-1',
            symbol: '0700.HK',
            toolType: 'price_note',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#fb7185', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0 },
            anchors: [{ time: '2026-03-19', price: 545 }],
            payload: { text: '观察位' },
          },
        ],
        draftAnchors: null,
        activeTool: 'select',
        selectedDrawingId: 'note-1',
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

    await overlay.trigger('mousemove', { clientX: 150, clientY: 60 });
    await wrapper.get('[data-role="price-note-label-note-1"]').trigger('dblclick');
    const input = wrapper.get('[data-role="price-note-editor-input"]');
    await input.trigger('keydown.esc');
    expect(wrapper.emitted('labelEditingChange')?.slice(-2)).toEqual([[true], [false]]);

    await overlay.trigger('mousemove', { clientX: 150, clientY: 60 });
    await wrapper.get('[data-role="price-note-label-note-1"]').trigger('dblclick');
    await wrapper.get('[data-role="price-note-editor-input"]').trigger('blur');
    expect(wrapper.emitted('labelEditingChange')?.slice(-2)).toEqual([[true], [false]]);
  });

  it('stops escape from bubbling after consuming overlay-local keyboard actions', async () => {
    const windowKeydownSpy = vi.fn();
    window.addEventListener('keydown', windowKeydownSpy);

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
    await overlay.trigger('keydown', { key: 'Escape' });
    expect(wrapper.emitted('draftCancel')).toHaveLength(1);
    expect(windowKeydownSpy).not.toHaveBeenCalled();
    window.removeEventListener('keydown', windowKeydownSpy);
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

  it('hands empty-space gestures back to the underlying chart element', async () => {
    const underlying = document.createElement('div');
    const mouseDownSpy = vi.fn();
    const wheelSpy = vi.fn();
    underlying.addEventListener('mousedown', mouseDownSpy);
    underlying.addEventListener('wheel', wheelSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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

    await overlay.trigger('mousedown', { clientX: 200, clientY: 60, button: 0, buttons: 1 });
    expect(mouseDownSpy).toHaveBeenCalledTimes(1);

    overlay.element.dispatchEvent(
      new WheelEvent('wheel', {
        bubbles: true,
        cancelable: true,
        clientX: 200,
        clientY: 60,
        deltaY: -20,
      }),
    );
    expect(wheelSpy).toHaveBeenCalledTimes(1);

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });

  it('keeps gesture ownership when pressing on a drawing body', async () => {
    const underlying = document.createElement('div');
    const mouseDownSpy = vi.fn();
    underlying.addEventListener('mousedown', mouseDownSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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
            locked: false,
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

    await overlay.trigger('mousemove', { clientX: 120, clientY: 40 });
    await wrapper.get('[data-role="drawing-body-horizontal-1"]').trigger('mousedown', { clientX: 120, clientY: 40, button: 0, buttons: 1 });
    expect(mouseDownSpy).not.toHaveBeenCalled();

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });

  it('supports additive selection with shift-click and clears selection on blank click', async () => {
    const wrapper = mount(KlineDrawingOverlay, {
      props: {
        symbol: '0700.HK',
        candles: [
          { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
          { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
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
          {
            id: 'horizontal-1',
            symbol: '0700.HK',
            toolType: 'horizontal_line',
            createdAt: '2026-03-27T00:00:00.000Z',
            updatedAt: '2026-03-27T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
            anchors: [{ time: '2026-03-18', price: 540 }],
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

    await overlay.trigger('mousemove', { clientX: 120, clientY: 66 });
    await wrapper.get('[data-role="drawing-body-horizontal-1"]').trigger('click', { clientX: 120, clientY: 66, shiftKey: true });
    expect(wrapper.emitted('drawingSelect')?.[0]?.[0]).toEqual({ id: 'horizontal-1', append: true });

    await overlay.trigger('click', { clientX: 280, clientY: 100 });
    expect(wrapper.emitted('drawingSelect')?.[1]?.[0]).toEqual({ id: null, append: false });
  });

  it('hands empty-space touch gestures back to the underlying chart element and suppresses default scroll', async () => {
    const underlying = document.createElement('div');
    const touchStartSpy = vi.fn();
    const touchMoveSpy = vi.fn();
    const touchEndSpy = vi.fn();
    underlying.addEventListener('touchstart', touchStartSpy);
    underlying.addEventListener('touchmove', touchMoveSpy);
    underlying.addEventListener('touchend', touchEndSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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

    const startEvent = dispatchTouchEvent(overlay.element, 'touchstart', { clientX: 200, clientY: 60 });
    expect(touchStartSpy).toHaveBeenCalledTimes(1);
    expect(startEvent.defaultPrevented).toBe(true);

    const moveEvent = dispatchTouchEvent(window.document, 'touchmove', { clientX: 180, clientY: 60 });
    expect(touchMoveSpy).toHaveBeenCalledTimes(1);
    expect(moveEvent.defaultPrevented).toBe(true);

    const endEvent = dispatchTouchEvent(window.document, 'touchend', { clientX: 180, clientY: 60 });
    expect(touchEndSpy).toHaveBeenCalledTimes(1);
    expect(endEvent.defaultPrevented).toBe(true);
    expect((overlay.element as HTMLElement).style.pointerEvents).toBe('');

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });

  it('keeps touch gesture ownership when pressing on a drawing body', async () => {
    const underlying = document.createElement('div');
    const touchStartSpy = vi.fn();
    underlying.addEventListener('touchstart', touchStartSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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
            locked: false,
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

    await overlay.trigger('mousemove', { clientX: 120, clientY: 45 });
    const drawingBody = wrapper.get('[data-role="drawing-body-horizontal-1"]');
    const startEvent = dispatchTouchEvent(drawingBody.element, 'touchstart', { clientX: 120, clientY: 45 });
    expect(touchStartSpy).not.toHaveBeenCalled();
    expect(startEvent.defaultPrevented).toBe(false);

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });

  it('does not hand touch gestures to the chart outside select mode', async () => {
    const underlying = document.createElement('div');
    const touchStartSpy = vi.fn();
    underlying.addEventListener('touchstart', touchStartSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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

    const startEvent = dispatchTouchEvent(overlay.element, 'touchstart', { clientX: 200, clientY: 60 });
    expect(touchStartSpy).not.toHaveBeenCalled();
    expect(startEvent.defaultPrevented).toBe(false);

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });

  it('preserves multi-touch sequences for the underlying chart', async () => {
    const underlying = document.createElement('div');
    const touchStartSpy = vi.fn();
    const touchMoveSpy = vi.fn();
    underlying.addEventListener('touchstart', touchStartSpy);
    underlying.addEventListener('touchmove', touchMoveSpy);
    document.body.appendChild(underlying);

    const elementFromPointSpy = vi.spyOn(document, 'elementFromPoint').mockImplementation(() => underlying);

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

    dispatchTouchEvent(overlay.element, 'touchstart', {
      touches: [
        { clientX: 120, clientY: 60 },
        { clientX: 180, clientY: 60 },
      ],
    });
    expect(touchStartSpy).toHaveBeenCalledTimes(1);
    expect((touchStartSpy.mock.calls[0]?.[0] as Event & { touches: Array<unknown> }).touches).toHaveLength(2);

    dispatchTouchEvent(window.document, 'touchmove', {
      touches: [
        { clientX: 100, clientY: 60 },
        { clientX: 200, clientY: 60 },
      ],
    });
    expect(touchMoveSpy).toHaveBeenCalledTimes(1);
    expect((touchMoveSpy.mock.calls[0]?.[0] as Event & { touches: Array<unknown> }).touches).toHaveLength(2);

    elementFromPointSpy.mockRestore();
    underlying.remove();
  });
});
