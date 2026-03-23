import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let addSeriesMock: ReturnType<typeof vi.fn>;
let chartMock: ReturnType<typeof vi.fn>;

vi.mock('lightweight-charts', () => ({
  createChart: (...args: unknown[]) => chartMock(...args),
  LineSeries: Symbol('LineSeries'),
}));

import StockSparkline from './StockSparkline.vue';

describe('StockSparkline', () => {
  beforeEach(() => {
    addSeriesMock = vi.fn(() => ({
      setData: vi.fn(),
    }));
    chartMock = vi.fn(() => ({
      addSeries: addSeriesMock,
      remove: vi.fn(),
      timeScale: () => ({ fitContent: vi.fn() }),
    }));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('creates a lightweight chart line series for sparkline prices', () => {
    mount(StockSparkline, {
      props: {
        prices: [100, 102, 101, 105],
      },
      attachTo: document.body,
    });

    expect(chartMock).toHaveBeenCalledTimes(1);
    expect(addSeriesMock).toHaveBeenCalledTimes(1);
  });
});
