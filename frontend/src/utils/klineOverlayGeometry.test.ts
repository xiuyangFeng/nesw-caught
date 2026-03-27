import { describe, expect, it } from 'vitest';

import type { KlineCandle, KlineDrawing } from '../types/api';
import {
  buildCrosshairProjection,
  findAnchorHandleIndex,
  findNearestCandleIndex,
  moveDrawingByAnchor,
  moveDrawingByDelta,
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
});
