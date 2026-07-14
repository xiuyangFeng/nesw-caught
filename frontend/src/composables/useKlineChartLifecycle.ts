import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { computed, type ComputedRef, type Ref } from 'vue';

import type { KlineCandle, KlineSubIndicator, StockKlineResponse } from '../types/api';
import { calculateRsi, type RenderedOverlayLine } from '../utils/klineIndicators';

type UseKlineChartLifecycleOptions = {
  mainChartRef: Ref<HTMLElement | null>;
  subChartRef: Ref<HTMLElement | null>;
  candles: ComputedRef<KlineCandle[]>;
  activeLines: ComputedRef<RenderedOverlayLine[]>;
  activeSubIndicator: ComputedRef<KlineSubIndicator>;
  klineData: ComputedRef<StockKlineResponse | null>;
  onMarkersBind?: (candleSeries: ISeriesApi<'Candlestick'> | null) => void;
};

export function useKlineChartLifecycle(options: UseKlineChartLifecycleOptions) {
  const { mainChartRef, subChartRef, candles, activeLines, activeSubIndicator, klineData, onMarkersBind } = options;

  let chart: IChartApi | null = null;
  let subChart: IChartApi | null = null;
  let candleSeries: ISeriesApi<'Candlestick'> | null = null;
  let volumeSeries: ISeriesApi<'Histogram'> | null = null;
  let macdHistogramSeries: ISeriesApi<'Histogram'> | null = null;
  let macdDifSeries: ISeriesApi<'Line'> | null = null;
  let macdDeaSeries: ISeriesApi<'Line'> | null = null;
  let kSeries: ISeriesApi<'Line'> | null = null;
  let dSeries: ISeriesApi<'Line'> | null = null;
  let jSeries: ISeriesApi<'Line'> | null = null;
  let rsiSeries: ISeriesApi<'Line'> | null = null;
  const lineSeriesMap = new Map<string, ISeriesApi<'Line'>>();

  const chartProjector = computed(() => ({
    getXForTime(time: string) {
      return (chart?.timeScale() as { timeToCoordinate?: (value: string) => number | null } | undefined)?.timeToCoordinate?.(time) ?? null;
    },
    getTimeForX(x: number) {
      return (chart?.timeScale() as { coordinateToTime?: (value: number) => string | null } | undefined)?.coordinateToTime?.(x) ?? null;
    },
    getYForPrice(price: number) {
      return (candleSeries as { priceToCoordinate?: (value: number) => number | null } | null)?.priceToCoordinate?.(price) ?? null;
    },
    getPriceForY(y: number) {
      return (candleSeries as { coordinateToPrice?: (value: number) => number | null } | null)?.coordinateToPrice?.(y) ?? null;
    },
  }));

  function getChart() {
    return chart;
  }

  function getSubChart() {
    return subChart;
  }

  function ensureChart() {
    if (chart || !mainChartRef.value) {
      return;
    }
    chart = createChart(mainChartRef.value, {
      autoSize: true,
      height: 420,
      layout: {
        background: { color: 'transparent' },
        textColor: 'rgba(226,232,240,0.72)',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(150,160,200,0.08)' },
        horzLines: { color: 'rgba(150,160,200,0.08)' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    // 红涨绿跌：对齐设计令牌 --positive(#ff5a72) / --negative(#1fd39a)
    candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ff5a72',
      downColor: '#1fd39a',
      borderUpColor: '#ff5a72',
      borderDownColor: '#1fd39a',
      wickUpColor: '#ff5a72',
      wickDownColor: '#1fd39a',
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  function ensureSubChart() {
    if (subChart || !subChartRef.value) {
      return;
    }
    subChart = createChart(subChartRef.value, {
      autoSize: true,
      height: 140,
      layout: {
        background: { color: 'transparent' },
        textColor: 'rgba(148,163,184,0.72)',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(150,160,200,0.06)' },
        horzLines: { color: 'rgba(150,160,200,0.08)' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    volumeSeries = subChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
      color: 'rgba(58,210,230,0.28)',
    });
    macdHistogramSeries = subChart.addSeries(HistogramSeries, {
      priceLineVisible: false,
      lastValueVisible: false,
      color: 'rgba(58,210,230,0.28)',
    });
    macdDifSeries = subChart.addSeries(LineSeries, {
      color: '#3ad2e6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    macdDeaSeries = subChart.addSeries(LineSeries, {
      color: '#7dd3fc',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    kSeries = subChart.addSeries(LineSeries, {
      color: '#3ad2e6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    dSeries = subChart.addSeries(LineSeries, {
      color: '#7dd3fc',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    jSeries = subChart.addSeries(LineSeries, {
      color: '#fb7185',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    rsiSeries = subChart.addSeries(LineSeries, {
      color: '#34d399',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  function ensureLineSeries(key: string, color: string, lineStyle?: 0 | 2) {
    ensureChart();
    if (!chart) {
      return null;
    }
    if (!lineSeriesMap.has(key)) {
      lineSeriesMap.set(
        key,
        chart.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          lineStyle,
          priceLineVisible: false,
          lastValueVisible: false,
        }),
      );
    }
    return lineSeriesMap.get(key) ?? null;
  }

  function clearSubChart() {
    volumeSeries?.setData([]);
    macdHistogramSeries?.setData([]);
    macdDifSeries?.setData([]);
    macdDeaSeries?.setData([]);
    kSeries?.setData([]);
    dSeries?.setData([]);
    jSeries?.setData([]);
    rsiSeries?.setData([]);
  }

  function renderSubChart() {
    ensureSubChart();
    if (!subChart || !klineData.value) {
      clearSubChart();
      return;
    }
    clearSubChart();
    if (activeSubIndicator.value === 'VOL') {
      volumeSeries?.setData(
        klineData.value.candles.map((candle) => ({
          time: candle.time,
          value: candle.volume ?? 0,
          color: candle.close >= candle.open ? 'rgba(255,90,114,0.5)' : 'rgba(31,211,154,0.42)',
        })),
      );
    } else if (activeSubIndicator.value === 'MACD') {
      // 后端 IndicatorSeriesView.macd/kdj 为可选字段(缺省即空序列),兜底为空数组
      const macd = klineData.value.indicators.macd ?? [];
      macdHistogramSeries?.setData(
        macd.map((point) => ({
          time: point.time,
          value: point.histogram,
          color: point.histogram >= 0 ? 'rgba(255,90,114,0.5)' : 'rgba(31,211,154,0.42)',
        })),
      );
      macdDifSeries?.setData(macd.map((point) => ({ time: point.time, value: point.dif })));
      macdDeaSeries?.setData(macd.map((point) => ({ time: point.time, value: point.dea })));
    } else if (activeSubIndicator.value === 'KDJ') {
      const kdj = klineData.value.indicators.kdj ?? [];
      kSeries?.setData(kdj.map((point) => ({ time: point.time, value: point.k })));
      dSeries?.setData(kdj.map((point) => ({ time: point.time, value: point.d })));
      jSeries?.setData(kdj.map((point) => ({ time: point.time, value: point.j })));
    } else {
      rsiSeries?.setData(
        calculateRsi(klineData.value.candles, 14)
          .filter((point) => !Number.isNaN(point.value))
          .map((point) => ({ time: point.time, value: point.value })),
      );
    }
    subChart.timeScale().fitContent();
  }

  function renderChart() {
    ensureChart();
    if (!chart || !candleSeries) {
      return;
    }
    candleSeries.setData(
      candles.value.map((candle) => ({
        time: candle.time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      })),
    );
    const activeKeys = new Set(activeLines.value.map((item) => item.key));
    activeLines.value.forEach((item) => {
      ensureLineSeries(item.key, item.color, item.lineStyle)?.setData(item.points.filter((point) => !Number.isNaN(point.value)));
    });
    lineSeriesMap.forEach((series, key) => {
      if (!activeKeys.has(key)) {
        series.setData([]);
      }
    });
    chart.timeScale().fitContent();
    renderSubChart();
    onMarkersBind?.(candleSeries);
  }

  function destroyCharts() {
    chart?.remove();
    subChart?.remove();
    chart = null;
    subChart = null;
    candleSeries = null;
    volumeSeries = null;
    macdHistogramSeries = null;
    macdDifSeries = null;
    macdDeaSeries = null;
    kSeries = null;
    dSeries = null;
    jSeries = null;
    rsiSeries = null;
    lineSeriesMap.clear();
  }

  return {
    chartProjector,
    renderChart,
    destroyCharts,
    getChart,
    getSubChart,
  };
}
