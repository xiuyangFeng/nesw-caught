import type {
  KlineCandle,
  KlineIndicatorTemplate,
  KlineSubIndicator,
  KlineValuePoint,
} from '../types/api';

export interface RenderedOverlayLine {
  key: string;
  label: string;
  color: string;
  points: KlineValuePoint[];
  lineStyle?: 0 | 2;
}

const MA_COLORS = ['#ffd166', '#7dd3fc', '#c084fc', '#fb7185', '#34d399', '#f59e0b'];
const EMA_COLORS = ['#ff9f2f', '#38bdf8', '#f472b6', '#22c55e'];

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function round(value: number) {
  return Number(value.toFixed(4));
}

export function calculateMovingAverage(candles: KlineCandle[], period: number): KlineValuePoint[] {
  if (period <= 0) {
    return [];
  }
  return candles.map((candle, index) => {
    if (index + 1 < period) {
      return { time: candle.time, value: Number.NaN };
    }
    const slice = candles.slice(index + 1 - period, index + 1).map((item) => item.close);
    return { time: candle.time, value: round(average(slice)) };
  });
}

export function calculateEma(candles: KlineCandle[], period: number): KlineValuePoint[] {
  if (!candles.length || period <= 0) {
    return [];
  }
  const multiplier = 2 / (period + 1);
  let prev = candles[0].close;
  return candles.map((candle, index) => {
    if (index === 0) {
      prev = candle.close;
      return { time: candle.time, value: round(prev) };
    }
    prev = candle.close * multiplier + prev * (1 - multiplier);
    return { time: candle.time, value: round(prev) };
  });
}

export function calculateRsi(candles: KlineCandle[], period: number): KlineValuePoint[] {
  if (!candles.length || period <= 0) {
    return [];
  }
  let avgGain = 0;
  let avgLoss = 0;
  return candles.map((candle, index) => {
    if (index === 0) {
      return { time: candle.time, value: Number.NaN };
    }
    const change = candle.close - candles[index - 1].close;
    const gain = Math.max(change, 0);
    const loss = Math.max(-change, 0);
    if (index <= period) {
      avgGain += gain;
      avgLoss += loss;
      if (index === period) {
        avgGain /= period;
        avgLoss /= period;
      }
      return { time: candle.time, value: Number.NaN };
    }
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    if (avgLoss === 0) {
      return { time: candle.time, value: 100 };
    }
    const rs = avgGain / avgLoss;
    return { time: candle.time, value: round(100 - 100 / (1 + rs)) };
  });
}

export function buildOverlayLines(template: KlineIndicatorTemplate, candles: KlineCandle[]) {
  const lines: RenderedOverlayLine[] = [];
  template.overlayIndicators.forEach((indicator) => {
    if (!indicator.visible) {
      return;
    }
    if (indicator.kind === 'MA') {
      indicator.params.periods.forEach((period, index) => {
        lines.push({
          key: `ma-${period}`,
          label: `MA${period}`,
          color: MA_COLORS[index % MA_COLORS.length],
          points: calculateMovingAverage(candles, period),
        });
      });
      return;
    }
    if (indicator.kind === 'EMA') {
      indicator.params.periods.forEach((period, index) => {
        lines.push({
          key: `ema-${period}`,
          label: `EMA${period}`,
          color: EMA_COLORS[index % EMA_COLORS.length],
          points: calculateEma(candles, period),
        });
      });
      return;
    }
    if (indicator.kind === 'BOLL') {
      const base = calculateMovingAverage(candles, indicator.params.period);
      const upper: KlineValuePoint[] = [];
      const middle: KlineValuePoint[] = [];
      const lower: KlineValuePoint[] = [];
      candles.forEach((candle, index) => {
        if (index + 1 < indicator.params.period) {
          upper.push({ time: candle.time, value: Number.NaN });
          middle.push({ time: candle.time, value: Number.NaN });
          lower.push({ time: candle.time, value: Number.NaN });
          return;
        }
        const slice = candles.slice(index + 1 - indicator.params.period, index + 1).map((item) => item.close);
        const mean = average(slice);
        const variance = average(slice.map((item) => (item - mean) ** 2));
        const deviation = Math.sqrt(variance) * indicator.params.stdDev;
        upper.push({ time: candle.time, value: round(mean + deviation) });
        middle.push(base[index]);
        lower.push({ time: candle.time, value: round(mean - deviation) });
      });
      lines.push({ key: 'boll-upper', label: 'BOLL上轨', color: 'rgba(52,211,153,0.65)', points: upper });
      lines.push({
        key: 'boll-middle',
        label: 'BOLL中轨',
        color: 'rgba(52,211,153,0.45)',
        points: middle,
        lineStyle: 2,
      });
      lines.push({ key: 'boll-lower', label: 'BOLL下轨', color: 'rgba(52,211,153,0.65)', points: lower });
    }
  });
  return lines;
}

export function resolveSubIndicator(template: KlineIndicatorTemplate | null | undefined): KlineSubIndicator {
  return template?.subIndicator ?? 'VOL';
}
