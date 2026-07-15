import { describe, expect, it } from 'vitest';

import type { KlineCandle, KlineDrawing } from '../types/api';
import {
  buildCrosshairProjection,
  computeAnchorFromPoint,
  computeCandleIndexDelta,
  computeFibonacciLevels,
  findAnchorHandleIndex,
  findNearestCandleIndex,
  moveDrawingByAnchor,
  moveDrawingByDelta,
  normalizeTouchPoint,
  projectAnchorToPoint,
  resolveEventClientPoint,
  toLocalPoint,
  touchPointFromEvent,
  touchPointsFromEvent,
} from './klineOverlayGeometry';

const candles: KlineCandle[] = [
  { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
  { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
  { time: '2026-03-20', open: 551, high: 560, low: 545, close: 558.3, volume: 980 },
];

describe('klineOverlayGeometry', () => {
  it('finds the nearest candle index from pixel position', () => {
    expect(findNearestCandleIndex(10, 300, candles.length)).toBe(0);
    expect(findNearestCandleIndex(140, 300, candles.length)).toBe(1);
    expect(findNearestCandleIndex(299, 300, candles.length)).toBe(2);
  });

  it('finds anchor handles and replaces a specific anchor', () => {
    expect(
      findAnchorHandleIndex(
        { x: 24, y: 33 },
        [
          { x: 20, y: 30 },
          { x: 120, y: 90 },
        ],
      ),
    ).toBe(0);

    const drawing: KlineDrawing = {
      id: 'trend-1',
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
    };

    expect(moveDrawingByAnchor(drawing, 1, { time: '2026-03-20', price: 558.3 })).toEqual([
      { time: '2026-03-18', price: 533.2 },
      { time: '2026-03-20', price: 558.3 },
    ]);
  });

  it('moves trend lines, ranges, and horizontal lines with the expected deltas', () => {
    const base = {
      symbol: '0700.HK',
      createdAt: '2026-03-27T00:00:00.000Z',
      updatedAt: '2026-03-27T00:00:00.000Z',
      locked: false,
      visible: true,
      style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid' as const, fillOpacity: 0.18 },
      payload: {},
    };

    expect(
      moveDrawingByDelta(
        {
          ...base,
          id: 'trend-1',
          toolType: 'trend_line' as const,
          anchors: [
            { time: '2026-03-18', price: 533.2 },
            { time: '2026-03-19', price: 550.5 },
          ],
        },
        candles,
        1,
        5,
      ),
    ).toEqual([
      { time: '2026-03-19', price: 538.2 },
      { time: '2026-03-20', price: 555.5 },
    ]);

    expect(
      moveDrawingByDelta(
        {
          ...base,
          id: 'range-1',
          toolType: 'price_range' as const,
          anchors: [
            { time: '2026-03-18', price: 532 },
            { time: '2026-03-19', price: 548 },
          ],
        },
        candles,
        1,
        3,
      ),
    ).toEqual([
      { time: '2026-03-19', price: 535 },
      { time: '2026-03-20', price: 551 },
    ]);

    expect(
      moveDrawingByDelta(
        {
          ...base,
          id: 'fib-1',
          toolType: 'fibonacci_retracement' as const,
          anchors: [
            { time: '2026-03-18', price: 560 },
            { time: '2026-03-19', price: 530 },
          ],
        },
        candles,
        1,
        -6,
      ),
    ).toEqual([
      { time: '2026-03-19', price: 554 },
      { time: '2026-03-20', price: 524 },
    ]);

    expect(
      moveDrawingByDelta(
        {
          ...base,
          id: 'horizontal-1',
          toolType: 'horizontal_line' as const,
          anchors: [{ time: '2026-03-18', price: 540 }],
        },
        candles,
        2,
        -4,
      ),
    ).toEqual([{ time: '2026-03-18', price: 536 }]);

    expect(
      moveDrawingByDelta(
        {
          ...base,
          id: 'note-1',
          toolType: 'price_note' as const,
          anchors: [{ time: '2026-03-18', price: 540 }],
          payload: { text: '540.00' },
        },
        candles,
        2,
        -4,
      ),
    ).toEqual([{ time: '2026-03-20', price: 536 }]);
  });

  it('builds a crosshair projection payload for labels', () => {
    expect(
      buildCrosshairProjection({
        anchor: { time: '2026-03-19', price: 550.5 },
        candles,
        width: 300,
        height: 120,
        projector: {
          getXForTime: (time) => (time === '2026-03-19' ? 164 : null),
          getYForPrice: (price) => (price === 550.5 ? 26 : null),
          getTimeLabel: () => '03-19 10:30',
          getPriceLabel: () => '550.55',
        },
      }),
    ).toMatchObject({
      timeLabel: '03-19 10:30',
      priceLabel: '550.55',
      x: 164,
      y: 26,
    });
  });

  it('computes the candle index delta between a start and target time', () => {
    expect(computeCandleIndexDelta(candles, '2026-03-18', '2026-03-20')).toBe(2);
    expect(computeCandleIndexDelta(candles, '2026-03-19', '2026-03-18')).toBe(-1);
    // 找不到起点时按 0 兜底(与组件里 Math.max(startIndex, 0) 的行为一致)。
    expect(computeCandleIndexDelta(candles, 'missing', '2026-03-19')).toBe(1);
  });

  it('computes fibonacci retracement levels from two projected points, or an empty list otherwise', () => {
    const levels = computeFibonacciLevels([
      { x: 0, y: 0 },
      { x: 10, y: 100 },
    ]);
    expect(levels).toHaveLength(7);
    expect(levels[0]).toEqual({ key: '0', y: 0, label: '0' });
    expect(levels[3]).toEqual({ key: '0.5', y: 50, label: '0.5' });
    expect(levels[6]).toEqual({ key: '1', y: 100, label: '1' });

    expect(computeFibonacciLevels([])).toEqual([]);
    expect(computeFibonacciLevels([{ x: 0, y: 0 }])).toEqual([]);
  });

  it('projects a drawing anchor to a pixel point within the overlay size', () => {
    expect(projectAnchorToPoint({ time: '2026-03-19', price: 550.5 }, candles, { width: 300, height: 120 })).toEqual({
      x: 150,
      y: 38,
    });

    // 找不到精确匹配的蜡烛时间时回退到最近的历史蜡烛(remapAnchorTime)。
    expect(projectAnchorToPoint({ time: '2026-03-19T12:00:00', price: 550.5 }, candles, { width: 300, height: 120 })).toEqual({
      x: 150,
      y: 38,
    });

    expect(projectAnchorToPoint({ time: '2026-03-18', price: 550.5 }, [], { width: 300, height: 120 })).toBeNull();

    // 单蜡烛且最高价等于最低价时,退化到画布正中心。
    const flatCandles: KlineCandle[] = [{ time: '2026-03-18', open: 540, high: 540, low: 540, close: 540, volume: 10 }];
    expect(projectAnchorToPoint({ time: '2026-03-18', price: 540 }, flatCandles, { width: 300, height: 120 })).toEqual({
      x: 150,
      y: 60,
    });
  });

  it('computes a drawing anchor from a client point, falling back to interpolated price when no projector resolves it', () => {
    expect(
      computeAnchorFromPoint({ clientX: 150, clientY: 60 }, { left: 0, top: 0, width: 300, height: 120 }, candles),
    ).toEqual({ time: '2026-03-19', price: 545 });

    expect(
      computeAnchorFromPoint({ clientX: 150, clientY: 60 }, { left: 0, top: 0, width: 300, height: 120 }, candles, {
        getTimeForX: (x) => (x === 150 ? '2026-03-20' : null),
        getPriceForY: (y) => (y === 60 ? 555 : null),
      }),
    ).toEqual({ time: '2026-03-20', price: 555 });

    expect(computeAnchorFromPoint({ clientX: 0, clientY: 0 }, { left: 0, top: 0, width: 10, height: 10 }, [])).toBeNull();
  });

  it('normalizes touch points and derives client points from mouse/touch events', () => {
    expect(normalizeTouchPoint({ clientX: 10, clientY: 20 })).toEqual({
      clientX: 10,
      clientY: 20,
      pageX: 10,
      pageY: 20,
      screenX: 10,
      screenY: 20,
    });
    expect(normalizeTouchPoint({ clientX: 5, clientY: 6, pageX: 7, pageY: 8, screenX: 9, screenY: 11 })).toEqual({
      clientX: 5,
      clientY: 6,
      pageX: 7,
      pageY: 8,
      screenX: 9,
      screenY: 11,
    });

    const touchesEvent = { touches: [{ clientX: 1, clientY: 2 }], changedTouches: [{ clientX: 3, clientY: 4 }] } as unknown as TouchEvent;
    expect(touchPointsFromEvent(touchesEvent)).toEqual([{ clientX: 1, clientY: 2, pageX: 1, pageY: 2, screenX: 1, screenY: 2 }]);

    // touches 为空时回退到 changedTouches(touchend/touchcancel 场景)。
    const changedOnlyEvent = { touches: [], changedTouches: [{ clientX: 9, clientY: 8 }] } as unknown as TouchEvent;
    expect(touchPointFromEvent(changedOnlyEvent)).toEqual({ clientX: 9, clientY: 8, pageX: 9, pageY: 8, screenX: 9, screenY: 8 });

    const emptyEvent = { touches: [], changedTouches: [] } as unknown as TouchEvent;
    expect(touchPointFromEvent(emptyEvent)).toBeNull();

    const mouseEvent = new MouseEvent('mousedown', { clientX: 12, clientY: 34 });
    expect(resolveEventClientPoint(mouseEvent)).toEqual({ clientX: 12, clientY: 34 });
    expect(resolveEventClientPoint(touchesEvent)).toEqual({ clientX: 1, clientY: 2 });
    expect(resolveEventClientPoint(emptyEvent)).toBeNull();

    expect(toLocalPoint({ clientX: 120, clientY: 80 }, { left: 20, top: 10 })).toEqual({ x: 100, y: 70 });
  });
});
