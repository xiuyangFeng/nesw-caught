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
      </div>
    `,
  },
}));

let addSeriesMock: ReturnType<typeof vi.fn>;
let chartMock: ReturnType<typeof vi.fn>;
let seriesMocks: Array<{ setData: ReturnType<typeof vi.fn> }>;

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
      const series = { setData: vi.fn() };
      seriesMocks.push(series);
      return series;
    });
    chartMock = vi.fn(() => ({
      addSeries: addSeriesMock,
      remove: vi.fn(),
      timeScale: () => ({ fitContent: vi.fn() }),
    }));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders trading-desk chrome, preserves chart rendering, and emits focus-news from event chips', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { default: KlineChart } = await import('./KlineChart.vue');
    const { useWatchlistChartStore } = await import('../../stores/watchlistChartStore');
    const chartStore = useWatchlistChartStore();
    const event = { time: '2026-03-19', items: [{ id: 1, title: 'Mainland buyers lift sentiment', sentiment: 'positive' }] };
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
            macd: [],
            kdj: [],
            bollinger: [{ time: '2026-03-19', upper: 556, middle: 547, lower: 538 }],
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
    ];
    chartStore.selectedDrawingId = 'drawing-1';

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
    expect(wrapper.find('[data-role="period-chip-1W"]').attributes('data-active')).toBe('true');
    expect(wrapper.find('[data-role="kline-chart-stage"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('代码');
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('年K');
    expect(wrapper.find('[data-role="kline-stage-badges"]').text()).toContain('长期');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('开');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('550.5');
    expect(wrapper.find('[data-role="kline-hud"]').text()).toContain('成交量');
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

    await wrapper.find('[data-role="overlay-label-commit"]').trigger('click');
    expect(chartStore.drawingsBySymbol['0700.HK'][0]?.payload?.text).toBe('突破确认');

    await wrapper.find('[data-role="indicator-switch-macd"]').trigger('click');
    expect(wrapper.find('[data-role="kline-subindicator-panel"]').text()).toContain('DIF');

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
});
