import type { KlineCandle, KlineDrawing, KlineDrawingAnchor } from '../types/api';

export interface ProjectedPoint {
  x: number;
  y: number;
}

export interface CrosshairProjection {
  x: number;
  y: number;
  timeLabel: string;
  priceLabel: string;
}

function distance(left: ProjectedPoint, right: ProjectedPoint) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function findNearestCandleIndex(x: number, width: number, candleCount: number) {
  if (candleCount <= 1) {
    return 0;
  }
  const ratio = clamp(x / Math.max(width, 1), 0, 1);
  return Math.round(ratio * (candleCount - 1));
}

export function findAnchorHandleIndex(point: ProjectedPoint, projectedAnchors: ProjectedPoint[], threshold = 8) {
  return projectedAnchors.findIndex((anchor) => distance(point, anchor) <= threshold);
}

export function remapAnchorTime(anchor: KlineDrawingAnchor, candles: KlineCandle[]): string {
  if (!candles.length) {
    return anchor.time;
  }
  const exact = candles.find((candle) => candle.time === anchor.time);
  if (exact) {
    return exact.time;
  }
  const earlier = [...candles].reverse().find((candle) => candle.time <= anchor.time);
  if (earlier) {
    return earlier.time;
  }
  return candles[0]?.time ?? anchor.time;
}

function findCandleIndexForTime(time: string, candles: KlineCandle[]) {
  const index = candles.findIndex((candle) => candle.time === time);
  if (index >= 0) {
    return index;
  }
  const remapped = remapAnchorTime({ time, price: 0 }, candles);
  return Math.max(0, candles.findIndex((candle) => candle.time === remapped));
}

function shiftAnchorTime(time: string, candles: KlineCandle[], delta: number) {
  if (!candles.length) {
    return time;
  }
  const nextIndex = clamp(findCandleIndexForTime(time, candles) + delta, 0, candles.length - 1);
  return candles[nextIndex]?.time ?? time;
}

export function moveDrawingByAnchor(drawing: KlineDrawing, anchorIndex: number, nextAnchor: KlineDrawingAnchor) {
  return drawing.anchors.map((anchor, index) => (index === anchorIndex ? nextAnchor : anchor));
}

export function moveDrawingByDelta(drawing: KlineDrawing, candles: KlineCandle[], timeDelta: number, priceDelta: number) {
  if (drawing.toolType === 'horizontal_line') {
    return drawing.anchors.map((anchor) => ({ time: anchor.time, price: anchor.price + priceDelta }));
  }
  return drawing.anchors.map((anchor) => ({
    time: shiftAnchorTime(anchor.time, candles, timeDelta),
    price: anchor.price + priceDelta,
  }));
}

export function buildCrosshairProjection(input: {
  anchor: KlineDrawingAnchor | null;
  candles: KlineCandle[];
  width: number;
  height: number;
}): CrosshairProjection | null {
  const { anchor, candles, width, height } = input;
  if (!anchor || !candles.length) {
    return null;
  }
  const index = findCandleIndexForTime(anchor.time, candles);
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const x = candles.length > 1 ? (index / (candles.length - 1)) * width : width / 2;
  const y = high === low ? height / 2 : (1 - (anchor.price - low) / (high - low)) * height;
  return {
    x,
    y,
    timeLabel: candles[index]?.time ?? anchor.time,
    priceLabel: anchor.price.toFixed(2),
  };
}

export function moveAnchors(anchors: KlineDrawingAnchor[], time: string, priceDelta: number) {
  return anchors.map((anchor) => ({ time, price: anchor.price + priceDelta }));
}

export function hitTestDrawing(
  drawing: KlineDrawing,
  point: ProjectedPoint,
  projector: (anchor: KlineDrawingAnchor) => ProjectedPoint | null,
) {
  const projected = drawing.anchors.map(projector).filter((item): item is ProjectedPoint => item !== null);
  if (!projected.length) {
    return false;
  }
  if (drawing.toolType === 'horizontal_line' || drawing.toolType === 'price_note') {
    return Math.abs(point.y - projected[0].y) < 8;
  }
  if (drawing.toolType === 'price_range') {
    const [start, end] = projected;
    if (!start || !end) {
      return false;
    }
    return point.x >= Math.min(start.x, end.x) && point.x <= Math.max(start.x, end.x) && point.y >= Math.min(start.y, end.y) && point.y <= Math.max(start.y, end.y);
  }
  const [start, end] = projected;
  if (!start || !end) {
    return false;
  }
  const length = distance(start, end);
  const total = distance(start, point) + distance(point, end);
  return Math.abs(total - length) < 8;
}
