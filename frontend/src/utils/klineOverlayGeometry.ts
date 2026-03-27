import type { KlineCandle, KlineDrawing, KlineDrawingAnchor } from '../types/api';

export interface ProjectedPoint {
  x: number;
  y: number;
}

function distance(left: ProjectedPoint, right: ProjectedPoint) {
  return Math.hypot(left.x - right.x, left.y - right.y);
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
