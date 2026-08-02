import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@vue/devtools-api', () => ({
  setupDevtoolsPlugin: () => undefined,
}));

vi.mock('./KlineDrawingOverlay.vue', () => ({
  default: {
    props: ['activeTool', 'chartProjector'],
    emits: [
      'draftStart',
      'draftUpdate',
      'draftCommit',
      'draftCancel',
      'labelEditingChange',
      'drawingSelect',
      'hoverAnchorChange',
      'drawingAnchorCommit',
      'drawingMoveCommit',
      'drawingLabelCommit',
    ],
    template: `
      <div data-role="kline-drawing-overlay-stub">
        <span data-role="overlay-projector-ready">{{ chartProjector ? 'yes' : 'no' }}</span>
        <button
          data-role="overlay-select-append"
          @click="$emit('drawingSelect', { id: 'drawing-2', append: true })"
        >
          append
        </button>
        <button
          data-role="overlay-hover-anchor"
          @click="$emit('hoverAnchorChange', { time: '2026-03-18', price: 534 })"
        >
          hover
        </button>
        <button
          data-role="overlay-clear-hover"
          @click="$emit('hoverAnchorChange', null)"
        >
          clear
        </button>
        <button
          data-role="overlay-anchor-commit"
          @click="$emit('drawingAnchorCommit', 'drawing-1', [{ time: '2026-03-18', price: 531 }, { time: '2026-03-20', price: 559 }])"
        >
          anchor
        </button>
        <button
          data-role="overlay-move-commit"
          @click="$emit('drawingMoveCommit', 'drawing-1', [{ time: '2026-03-19', price: 537 }, { time: '2026-03-20', price: 554 }])"
        >
          move
        </button>
        <button
          data-role="overlay-label-commit"
          @click="$emit('drawingLabelCommit', 'drawing-1', '突破确认')"
        >
          label
        </button>
        <button
          data-role="overlay-label-editing-open"
          @click="$emit('labelEditingChange', true)"
        >
          label-open
        </button>
        <button
          data-role="overlay-label-editing-close"
          @click="$emit('labelEditingChange', false)"
        >
          label-close
        </button>
      </div>
    `,
  },
}));

let addSeriesMock: ReturnType<typeof vi.fn>;
let chartMock: ReturnType<typeof vi.fn>;
let seriesMocks: Array<{ setData: ReturnType<typeof vi.fn>; setMarkers: ReturnType<typeof vi.fn> }>;

vi.mock('lightweight-charts', () => ({
  createChart: (...args: unknown[]) => chartMock(...args),
  CandlestickSeries: Symbol('CandlestickSeries'),
  HistogramSeries: Symbol('HistogramSeries'),
  LineSeries: Symbol('LineSeries'),
}));

describe('KlineChart', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
      },
      configurable: true,
    });
    seriesMocks = [];
    addSeriesMock = vi.fn(() => {
      const series = { setData: vi.fn(), setMarkers: vi.fn() };
      seriesMocks.push(series);
      return series;
    });
    chartMock = vi.fn(() => ({
      addSeries: addSeriesMock,
      remove: vi.fn(),
      timeScale: () => ({ fitContent: vi.fn() }),
      subscribeCrosshairMove: vi.fn(),
      subscribeClick: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('does not mount news tooltip or popup until an event is present', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');

    mount(KlineChart, {
      props: {
        currentPeriod: '1D',
        klineData: {
          symbol: '0700.HK',
          interval: '1d',
          range: '1y',
          stale: false,
          candles: [{ time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 }],
          indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
          news_events: [],
        },
      },
      attachTo: document.body,
    });

    expect(warnSpy).not.toHaveBeenCalledWith(expect.stringContaining('Invalid prop: type check failed for prop "event"'));
    warnSpy.mockRestore();
  });

  it('clears stale news markers when the next payload has no news events', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');

    const wrapper = mount(KlineChart, {
      props: {
        currentPeriod: '1D',
        klineData: {
          symbol: '0700.HK',
          interval: '1d',
          range: '1y',
          stale: false,
          candles: [{ time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 }],
          indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
          news_events: [{ time: '2026-03-19', items: [{ id: 1, title: 'Tencent update', sentiment: 'positive', summary: 'AI expansion' }] }],
        },
      },
      attachTo: document.body,
    });

    expect(seriesMocks[0]?.setMarkers).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ time: '2026-03-19', text: '1' })]),
    );

    await wrapper.setProps({
      klineData: {
        symbol: '0700.HK',
        interval: '1d',
        range: '1y',
        stale: false,
        candles: [{ time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 }],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
    });

    expect(seriesMocks[0]?.setMarkers).toHaveBeenLastCalledWith([]);
  });

  it('renders trading-desk chrome, preserves chart rendering, and emits focus-news from event chips', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');
    const { default: KlineToolbar } = await import('./KlineToolbar.vue');
    const { useWatchlistChartStore } = await import('../../stores/watchlistChartStore');
    const chartStore = useWatchlistChartStore();
    const event = { time: '2026-03-19', items: [{ id: 1, title: 'Mainland buyers lift sentiment', sentiment: 'positive', summary: 'Southbound inflows accelerate' }] };
    const wrapper = mount(KlineChart, {
      props: {
        currentPeriod: '1W',
        klineData: {
          symbol: '0700.HK',
          interval: '1mo',
          range: 'max',
          stale: false,
          candles: [
            { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
            { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
          ],
          indicators: {
            ma5: [{ time: '2026-03-19', value: 548 }],
            ma10: [{ time: '2026-03-19', value: 544 }],
            ma20: [{ time: '2026-03-19', value: 542 }],
            ma60: [{ time: '2026-03-19', value: 538 }],
            macd: [
              { time: '2026-03-18', dif: 1.2, dea: 0.8, histogram: 0.4 },
              { time: '2026-03-19', dif: 2.4, dea: 1.6, histogram: 0.8 },
            ],
            kdj: [
              { time: '2026-03-18', k: 45, d: 40, j: 55 },
              { time: '2026-03-19', k: 58, d: 52, j: 70 },
            ],
            bollinger: [
              { time: '2026-03-18', upper: 548, middle: 540, lower: 532 },
              { time: '2026-03-19', upper: 556, middle: 547, lower: 538 },
            ],
          },
          news_events: [event],
        },
      },
      attachTo: document.body,
    });

    chartStore.drawingsBySymbol['0700.HK'] = [
      {
        id: 'drawing-1',
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
        id: 'drawing-2',
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
    ];
    chartStore.selectedDrawingId = 'drawing-1';
    chartStore.selectedDrawingIds = ['drawing-1'];

    expect(chartMock).toHaveBeenCalledTimes(2);
    expect(addSeriesMock).toHaveBeenCalled();
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA5');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA10');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA20');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA60');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('BOLL');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('日K');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('周K');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('月K');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('年K');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('收起面板');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('撤销');
    expect(wrapper.find('[data-role="kline-period-toolbar"]').text()).toContain('重做');
    expect(wrapper.find('[data-role="period-chip-1W"]').attributes('data-active')).toBe('true');
    expect(wrapper.find('[data-role="kline-chart-stage"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('代码');
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('年K');
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('长期');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('开');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('550.5');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('成交量');
    expect(wrapper.find('[data-role="kline-hud"]').classes()).toContain('top-20');
    expect(wrapper.find('[data-role="overlay-projector-ready"]').text()).toBe('yes');
    expect(wrapper.find('[data-role="kline-layout-shell"]').attributes('data-sidebar-collapsed')).toBe('false');
    expect(wrapper.find('[data-role="kline-chart-dashboard"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="toggle-dashboard"]').text()).toContain('收起面板');
    expect(wrapper.find('[data-role="kline-chart-dashboard"]').text()).toContain('模板库');
    expect(wrapper.find('[data-role="indicator-switch-vol"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="indicator-switch-vol"]').text()).toContain('成交量');
    expect(wrapper.find('[data-role="indicator-switch-macd"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="indicator-switch-kdj"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-subindicator-panel"]').text()).toContain('成交量');
    expect(wrapper.find('[data-role="kline-subindicator-strip"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-chart"]').text()).toContain('更新时间');
    expect(wrapper.find('[data-role="kline-event-chip-2026-03-19"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-chart-summary"]').exists()).toBe(false);

    await wrapper.find('[data-role="overlay-hover-anchor"]').trigger('click');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('533.2');

    await wrapper.find('[data-role="overlay-clear-hover"]').trigger('click');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('550.5');

    await wrapper.find('[data-role="overlay-anchor-commit"]').trigger('click');
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.anchors?.[1]).toEqual({ time: '2026-03-20', price: 559 });

    await wrapper.find('[data-role="overlay-move-commit"]').trigger('click');
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.anchors?.[0]).toEqual({ time: '2026-03-19', price: 537 });

    await wrapper.find('[data-role="overlay-select-append"]').trigger('click');
    expect(chartStore.selectedDrawingIds).toEqual(['drawing-1', 'drawing-2']);

    await wrapper.find('[data-role="overlay-label-commit"]').trigger('click');
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.payload?.text).toBe('突破确认');

    await wrapper.find('[data-role="indicator-switch-macd"]').trigger('click');
    expect(wrapper.find('[data-role="kline-subindicator-panel"]').text()).toContain('DIF');
    await wrapper.find('[data-role="overlay-hover-anchor"]').trigger('click');
    expect(wrapper.find('[data-role="kline-subindicator-panel"]').text()).toContain('1.2');

    await wrapper.find('[data-role="period-chip-1D"]').trigger('click');
    expect(wrapper.emitted('switchPeriod')?.[0]?.[0]).toBe('1D');

    await wrapper.find('[data-role="indicator-switch-kdj"]').trigger('click');
    expect(wrapper.find('[data-role="kline-subindicator-panel"]').text()).toContain('K');

    await wrapper.find('[data-role="toggle-dashboard"]').trigger('click');
    expect(wrapper.find('[data-role="kline-layout-shell"]').attributes('data-sidebar-collapsed')).toBe('true');
    expect(wrapper.find('[data-role="kline-chart-dashboard"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="toggle-dashboard"]').text()).toContain('展开面板');

    await wrapper.find('[data-role="toggle-dashboard"]').trigger('click');
    expect(wrapper.find('[data-role="kline-layout-shell"]').attributes('data-sidebar-collapsed')).toBe('false');
    expect(wrapper.find('[data-role="kline-chart-dashboard"]').exists()).toBe(true);

    await wrapper.find('[data-role="kline-event-chip-2026-03-19"]').trigger('click');
    expect(wrapper.emitted('focusNews')?.[0]?.[0]).toEqual(event);

    wrapper.getComponent(KlineToolbar).vm.$emit('undo');
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.payload?.text).not.toBe('突破确认');

    wrapper.getComponent(KlineToolbar).vm.$emit('undo');
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.anchors?.[0]).toEqual({ time: '2026-03-18', price: 531 });

    wrapper.getComponent(KlineToolbar).vm.$emit('redo');
    await wrapper.vm.$nextTick();
    wrapper.getComponent(KlineToolbar).vm.$emit('redo');
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.anchors?.[0]).toEqual({ time: '2026-03-19', price: 537 });

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true }));
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.payload?.text).not.toBe('突破确认');

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'y', ctrlKey: true }));
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.payload?.text).toBe('突破确认');

    await wrapper.setProps({ klineData: null });
    expect(seriesMocks.some((series) => series.setData.mock.calls.some((args) => Array.isArray(args[0]) && args[0].length === 0))).toBe(true);
    expect(wrapper.find('[data-role="kline-chart-empty-state"]').exists()).toBe(true);

    await wrapper.setProps({
      klineData: {
        symbol: 'BABA',
        interval: '1d',
        range: '1y',
        stale: false,
        candles: [{ time: '2026-03-21', open: 100, high: 110, low: 98, close: 108, volume: 800 }],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
    });
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('108');
    expect(chartStore.selectedDrawingId).toBeNull();
  });

  it('supports keyboard workbench actions for delete, escape, and nudging', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');
    const { useWatchlistChartStore } = await import('../../stores/watchlistChartStore');
    const chartStore = useWatchlistChartStore();
    const symbol = '0700.HK';

    const wrapper = mount(KlineChart, {
      props: {
        currentPeriod: '1D',
        klineData: {
          symbol,
          interval: '1d',
          range: '1y',
          stale: false,
          candles: [
            { time: '2026-03-18', open: 530, high: 540, low: 520, close: 535, volume: 1200 },
            { time: '2026-03-19', open: 535, high: 550, low: 530, close: 548, volume: 1000 },
            { time: '2026-03-20', open: 548, high: 560, low: 545, close: 558, volume: 980 },
            { time: '2026-03-21', open: 558, high: 565, low: 550, close: 552, volume: 920 },
            { time: '2026-03-24', open: 552, high: 570, low: 548, close: 568, volume: 1100 },
            { time: '2026-03-25', open: 568, high: 572, low: 560, close: 566, volume: 990 },
          ],
          indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
          news_events: [],
        },
      },
      attachTo: document.body,
    });

    chartStore.drawingsBySymbol[symbol] = [
      {
        id: 'drawing-1',
        symbol,
        toolType: 'trend_line',
        createdAt: '2026-03-27T00:00:00.000Z',
        updatedAt: '2026-03-27T00:00:00.000Z',
        locked: false,
        visible: true,
        style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
        anchors: [
          { time: '2026-03-18', price: 530 },
          { time: '2026-03-19', price: 548 },
        ],
        payload: {},
      },
      {
        id: 'drawing-2',
        symbol,
        toolType: 'horizontal_line',
        createdAt: '2026-03-27T00:00:00.000Z',
        updatedAt: '2026-03-27T00:00:00.000Z',
        locked: false,
        visible: true,
        style: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
        anchors: [{ time: '2026-03-18', price: 540 }],
        payload: {},
      },
    ];
    chartStore.selectedDrawingId = 'drawing-1';
    chartStore.selectedDrawingIds = ['drawing-1', 'drawing-2'];

    const deleteEvent = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
    const deletePreventSpy = vi.spyOn(deleteEvent, 'preventDefault');
    window.dispatchEvent(deleteEvent);
    await wrapper.vm.$nextTick();
    expect(deletePreventSpy).toHaveBeenCalled();
    expect(chartStore.drawingsBySymbol[symbol]).toHaveLength(0);
    expect(chartStore.selectedDrawingIds).toEqual([]);

    chartStore.undo(symbol);
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol[symbol]).toHaveLength(2);
    chartStore.selectDrawing('drawing-1');
    chartStore.selectDrawing('drawing-2', { append: true });

    const leftEvent = new KeyboardEvent('keydown', { key: 'ArrowLeft', cancelable: true });
    window.dispatchEvent(leftEvent);
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol[symbol][0]?.anchors[0]?.time).toBe('2026-03-18');
    expect(chartStore.drawingsBySymbol[symbol][0]?.anchors[1]?.time).toBe('2026-03-18');
    expect(chartStore.drawingsBySymbol[symbol][1]?.anchors[0]?.time).toBe('2026-03-18');

    const shiftUpEvent = new KeyboardEvent('keydown', { key: 'ArrowUp', shiftKey: true, cancelable: true });
    window.dispatchEvent(shiftUpEvent);
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol[symbol][0]?.anchors[0]?.price).toBeCloseTo(531.56);
    expect(chartStore.drawingsBySymbol[symbol][1]?.anchors[0]?.price).toBeCloseTo(541.56);

    chartStore.selectTool('trend_line');
    chartStore.startDraft({ time: '2026-03-18', price: 530 });
    const draftDeleteEvent = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
    window.dispatchEvent(draftDeleteEvent);
    await wrapper.vm.$nextTick();
    expect(chartStore.drawingsBySymbol[symbol]).toHaveLength(2);

    const escapeDraftEvent = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
    window.dispatchEvent(escapeDraftEvent);
    await wrapper.vm.$nextTick();
    expect(chartStore.draft).toBeNull();

    const escapeSelectionEvent = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
    window.dispatchEvent(escapeSelectionEvent);
    await wrapper.vm.$nextTick();
    expect(chartStore.selectedDrawingIds).toEqual([]);

    chartStore.selectDrawing('drawing-1');
    await wrapper.find('[data-role="overlay-label-editing-open"]').trigger('click');
    const blockedDeleteEvent = new KeyboardEvent('keydown', { key: 'Backspace', cancelable: true });
    const blockedDeletePreventSpy = vi.spyOn(blockedDeleteEvent, 'preventDefault');
    window.dispatchEvent(blockedDeleteEvent);
    await wrapper.vm.$nextTick();
    expect(blockedDeletePreventSpy).not.toHaveBeenCalled();
    expect(chartStore.drawingsBySymbol[symbol]).toHaveLength(2);
    await wrapper.find('[data-role="overlay-label-editing-close"]').trigger('click');

    const input = document.createElement('input');
    document.body.appendChild(input);
    chartStore.updateDrawingStyle(symbol, 'drawing-1', { color: '#000000' });
    input.focus();
    const focusedUndoEvent = new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, cancelable: true });
    const focusedUndoPreventSpy = vi.spyOn(focusedUndoEvent, 'preventDefault');
    window.dispatchEvent(focusedUndoEvent);
    await wrapper.vm.$nextTick();
    expect(focusedUndoPreventSpy).not.toHaveBeenCalled();
    expect(chartStore.drawingsBySymbol[symbol][0]?.style.color).toBe('#000000');

    const focusedArrowEvent = new KeyboardEvent('keydown', { key: 'ArrowRight', cancelable: true });
    const focusedArrowPreventSpy = vi.spyOn(focusedArrowEvent, 'preventDefault');
    window.dispatchEvent(focusedArrowEvent);
    await wrapper.vm.$nextTick();
    expect(focusedArrowPreventSpy).not.toHaveBeenCalled();
    input.remove();

    chartStore.clearSelection();
    const emptyDeleteEvent = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
    const emptyDeletePreventSpy = vi.spyOn(emptyDeleteEvent, 'preventDefault');
    window.dispatchEvent(emptyDeleteEvent);
    await wrapper.vm.$nextTick();
    expect(emptyDeletePreventSpy).not.toHaveBeenCalled();
  });

  it('filters out candles with null or non-finite price values gracefully', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');

    const wrapper = mount(KlineChart, {
      props: {
        klineData: {
          symbol: '0700.HK',
          interval: '1d',
          range: '6mo',
          stale: false,
          candles: [
            { time: '2026-03-18', open: 530, high: 540, low: 520, close: 535, volume: 1200 },
            { time: '2026-03-19', open: 535, high: 550, low: 530, close: null as unknown as number, volume: 1000 },
            { time: '2026-03-20', open: 548, high: 560, low: 545, close: 558, volume: 980 },
          ],
          indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
          news_events: [],
        },
      },
    });

    expect(wrapper.exists()).toBe(true);
    expect(seriesMocks.some((series) => series.setData.mock.calls.some((args) => Array.isArray(args[0]) && args[0].length === 2))).toBe(true);
  });
});
