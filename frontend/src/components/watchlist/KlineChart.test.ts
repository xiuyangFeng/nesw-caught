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

  it('creates chart series for candles, volume, and ma lines', () => {
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
            ma10: [],
            ma20: [],
            ma60: [],
            macd: [],
            kdj: [],
            bollinger: [],
          },
          news_events: [],
        },
      },
      attachTo: document.body,
    });

    expect(chartMock).toHaveBeenCalledTimes(1);
    expect(addSeriesMock).toHaveBeenCalled();
    wrapper.setProps({ klineData: null });
    expect(seriesMocks.some((series) => series.setData.mock.calls.some((args) => Array.isArray(args[0]) && args[0].length === 0))).toBe(true);
  });
});
