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

export interface KlineChartProjector {
  getXForTime?: (time: string) => number | null;
  getTimeForX?: (x: number) => string | null;
  getYForPrice?: (price: number) => number | null;
  getPriceForY?: (y: number) => number | null;
  getTimeLabel?: (time: string, x: number) => string | null;
  getPriceLabel?: (price: number, y: number) => string | null;
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
  if (drawing.toolType === 'price_note') {
    return drawing.anchors.map((anchor) => ({
      time: shiftAnchorTime(anchor.time, candles, timeDelta),
      price: anchor.price + priceDelta,
    }));
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
  projector?: KlineChartProjector | null;
}): CrosshairProjection | null {
  const { anchor, candles, width, height, projector } = input;
  if (!anchor || !candles.length) {
    return null;
  }
  const index = findCandleIndexForTime(anchor.time, candles);
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const fallbackX = candles.length > 1 ? (index / (candles.length - 1)) * width : width / 2;
  const fallbackY = high === low ? height / 2 : (1 - (anchor.price - low) / (high - low)) * height;
  const x = clamp(projector?.getXForTime?.(candles[index]?.time ?? anchor.time) ?? fallbackX, 0, width);
  const y = clamp(projector?.getYForPrice?.(anchor.price) ?? fallbackY, 0, height);
  const resolvedPrice = projector?.getPriceForY?.(y) ?? anchor.price;
  const resolvedTime = projector?.getTimeForX?.(x) ?? candles[index]?.time ?? anchor.time;
  return {
    x,
    y,
    timeLabel: projector?.getTimeLabel?.(resolvedTime, x) ?? resolvedTime,
    priceLabel: projector?.getPriceLabel?.(resolvedPrice, y) ?? resolvedPrice.toFixed(2),
  };
}

export function moveAnchors(anchors: KlineDrawingAnchor[], time: string, priceDelta: number) {
  return anchors.map((anchor) => ({ time, price: anchor.price + priceDelta }));
}

export function computeCandleIndexDelta(candles: KlineCandle[], fromTime: string, toTime: string) {
  const fromIndex = candles.findIndex((item) => item.time === fromTime);
  const toIndex = candles.findIndex((item) => item.time === toTime);
  return toIndex - Math.max(fromIndex, 0);
}

export interface FibonacciLevel {
  key: string;
  y: number;
  label: string;
}

export function computeFibonacciLevels(points: ProjectedPoint[]): FibonacciLevel[] {
  const [start, end] = points;
  if (!start || !end) {
    return [];
  }
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  return levels.map((level) => ({
    key: String(level),
    y: top + (bottom - top) * level,
    label: String(level),
  }));
}

export function projectAnchorToPoint(
  anchor: KlineDrawingAnchor,
  candles: KlineCandle[],
  size: { width: number; height: number },
): ProjectedPoint | null {
  if (!candles.length) {
    return null;
  }
  const mappedTime = remapAnchorTime(anchor, candles);
  const index = Math.max(
    0,
    candles.findIndex((candle) => candle.time === mappedTime),
  );
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const x = candles.length > 1 ? (index / (candles.length - 1)) * size.width : size.width / 2;
  const y = high === low ? size.height / 2 : (1 - (anchor.price - low) / (high - low)) * size.height;
  return { x, y };
}

export function computeAnchorFromPoint(
  clientPoint: { clientX: number; clientY: number },
  rect: { left: number; top: number; width: number; height: number },
  candles: KlineCandle[],
  chartProjector?: KlineChartProjector | null,
): KlineDrawingAnchor | null {
  if (!candles.length) {
    return null;
  }
  const index = findNearestCandleIndex(clientPoint.clientX - rect.left, rect.width, candles.length);
  const candle = candles[index];
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const ratio = 1 - (clientPoint.clientY - rect.top) / Math.max(rect.height, 1);
  const x = clientPoint.clientX - rect.left;
  const y = clientPoint.clientY - rect.top;
  const mappedTime = chartProjector?.getTimeForX?.(x);
  const projectedPrice = chartProjector?.getPriceForY?.(y);
  return {
    time: mappedTime ? remapAnchorTime({ time: mappedTime, price: projectedPrice ?? 0 }, candles) : candle.time,
    price: projectedPrice ?? low + (high - low) * ratio,
  };
}

// ---------------------------------------------------------------------------
// 指针/触摸事件坐标提取:从鼠标、滚轮、触摸事件中还原出统一的客户端坐标,
// 供命中检测与锚点换算复用。
// ---------------------------------------------------------------------------

export interface NormalizedTouchPoint {
  clientX: number;
  clientY: number;
  pageX: number;
  pageY: number;
  screenX: number;
  screenY: number;
}

export function normalizeTouchPoint(touch: {
  clientX: number;
  clientY: number;
  pageX?: number;
  pageY?: number;
  screenX?: number;
  screenY?: number;
}): NormalizedTouchPoint {
  return {
    clientX: touch.clientX,
    clientY: touch.clientY,
    pageX: touch.pageX ?? touch.clientX,
    pageY: touch.pageY ?? touch.clientY,
    screenX: touch.screenX ?? touch.clientX,
    screenY: touch.screenY ?? touch.clientY,
  };
}

export function touchPointsFromEvent(event: TouchEvent): NormalizedTouchPoint[] {
  return Array.from(event.touches.length ? event.touches : event.changedTouches).map((touch) => normalizeTouchPoint(touch));
}

export function touchPointFromEvent(event: TouchEvent): NormalizedTouchPoint | null {
  return touchPointsFromEvent(event)[0] ?? null;
}

export function resolveEventClientPoint(
  event: MouseEvent | WheelEvent | TouchEvent,
): { clientX: number; clientY: number } | null {
  // MouseEvent/WheelEvent 自带 clientX;TouchEvent(含测试里手工构造的
  // touch 事件对象)没有 clientX,只能从 touches/changedTouches 取坐标。
  if ('clientX' in event) {
    return {
      clientX: event.clientX,
      clientY: event.clientY,
    };
  }
  const touch = touchPointFromEvent(event);
  if (!touch) {
    return null;
  }
  return {
    clientX: touch.clientX,
    clientY: touch.clientY,
  };
}

export function toLocalPoint(
  clientPoint: { clientX: number; clientY: number },
  rect: { left: number; top: number },
): ProjectedPoint {
  return { x: clientPoint.clientX - rect.left, y: clientPoint.clientY - rect.top };
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
