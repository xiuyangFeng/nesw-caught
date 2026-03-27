import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let addSeriesMock: ReturnType<typeof vi.fn>;
let chartMock: ReturnType<typeof vi.fn>;
let seriesMocks: Array<{ setData: ReturnType<typeof vi.fn> }>;

vi.mock('lightweight-charts', () => ({
  createChart: (...args: unknown[]) => chartMock(...args),
  CandlestickSeries: Symbol('CandlestickSeries'),
  HistogramSeries: Symbol('HistogramSeries'),
  LineSeries: Symbol('LineSeries'),
}));

import KlineChart from './KlineChart.vue';

describe('KlineChart', () => {
  beforeEach(() => {
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
    const event = { time: '2026-03-19', items: [{ id: 1, title: 'Mainland buyers lift sentiment', sentiment: 'positive' }] };
    const wrapper = mount(KlineChart, {
      props: {
        klineData: {
          symbol: '0700.HK',
          interval: '1d',
          range: '6mo',
          stale: false,
          candles: [{ time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 }],
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

    expect(chartMock).toHaveBeenCalledTimes(1);
    expect(addSeriesMock).toHaveBeenCalled();
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA5');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA10');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA20');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('MA60');
    expect(wrapper.find('[data-role="kline-chart-legend"]').text()).toContain('BOLL');
    expect(wrapper.find('[data-role="kline-chart-summary"]').text()).toContain('0700.HK');
    expect(wrapper.find('[data-role="kline-chart-summary"]').text()).toContain('1d');
    expect(wrapper.find('[data-role="kline-chart-summary"]').text()).toContain('6mo');
    expect(wrapper.find('[data-role="kline-event-chip-2026-03-19"]').exists()).toBe(true);

    await wrapper.find('[data-role="kline-event-chip-2026-03-19"]').trigger('click');
    expect(wrapper.emitted('focusNews')?.[0]?.[0]).toEqual(event);

    await wrapper.setProps({ klineData: null });
    expect(seriesMocks.some((series) => series.setData.mock.calls.some((args) => Array.isArray(args[0]) && args[0].length === 0))).toBe(true);
    expect(wrapper.find('[data-role="kline-chart-empty-state"]').exists()).toBe(true);
  });
});
