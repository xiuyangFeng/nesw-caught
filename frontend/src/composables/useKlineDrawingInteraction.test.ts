import { describe, expect, it } from 'vitest';

import type { KlineCandle, KlineDrawing } from '../types/api';
import { useKlineDrawingInteraction } from './useKlineDrawingInteraction';

const candles: KlineCandle[] = [
  { time: '2026-03-18', open: 535, high: 546, low: 530, close: 533.2, volume: 1200 },
  { time: '2026-03-19', open: 540, high: 552, low: 538, close: 550.5, volume: 1000 },
  { time: '2026-03-20', open: 551, high: 560, low: 545, close: 558.3, volume: 980 },
];

function buildDrawing(overrides: Partial<KlineDrawing> = {}): KlineDrawing {
  return {
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
    ...overrides,
  };
}

describe('useKlineDrawingInteraction', () => {
  it('starts an anchor drag only for draggable drawings with a resolved anchor', () => {
    const interaction = useKlineDrawingInteraction();
    const drawing = buildDrawing();

    interaction.beginAnchorDrag(null, 0, { time: '2026-03-18', price: 533.2 });
    expect(interaction.dragState.value).toBeNull();

    interaction.beginAnchorDrag(drawing, 1, null);
    expect(interaction.dragState.value).toBeNull();

    interaction.beginAnchorDrag(buildDrawing({ locked: true }), 1, { time: '2026-03-18', price: 533.2 });
    expect(interaction.dragState.value).toBeNull();

    interaction.beginAnchorDrag(drawing, 1, { time: '2026-03-18', price: 533.2 });
    expect(interaction.dragState.value).toEqual({
      mode: 'anchor',
      drawingId: 'trend-1',
      anchorIndex: 1,
      startAnchor: { time: '2026-03-18', price: 533.2 },
    });
  });

  it('starts a body (object) drag only for draggable drawings with a resolved anchor', () => {
    const interaction = useKlineDrawingInteraction();
    const drawing = buildDrawing();

    interaction.beginBodyDrag(drawing, null);
    expect(interaction.dragState.value).toBeNull();

    interaction.beginBodyDrag(buildDrawing({ locked: true }), { time: '2026-03-18', price: 533.2 });
    expect(interaction.dragState.value).toBeNull();

    interaction.beginBodyDrag(drawing, { time: '2026-03-18', price: 530 });
    expect(interaction.dragState.value).toEqual({
      mode: 'object',
      drawingId: 'trend-1',
      startAnchor: { time: '2026-03-18', price: 530 },
    });
  });

  it('ends a drag and clears the state', () => {
    const interaction = useKlineDrawingInteraction();
    interaction.beginBodyDrag(buildDrawing(), { time: '2026-03-18', price: 530 });
    expect(interaction.dragState.value).not.toBeNull();

    interaction.endDrag();
    expect(interaction.dragState.value).toBeNull();
  });

  it('resolves an anchor-mode commit by replacing the dragged anchor', () => {
    const interaction = useKlineDrawingInteraction();
    const drawing = buildDrawing();

    interaction.beginAnchorDrag(drawing, 1, { time: '2026-03-19', price: 550.5 });
    const commit = interaction.resolveDragCommit(drawing, { time: '2026-03-20', price: 557.5 }, candles);

    expect(commit).toEqual({
      type: 'anchor',
      drawingId: 'trend-1',
      anchors: [
        { time: '2026-03-18', price: 533.2 },
        { time: '2026-03-20', price: 557.5 },
      ],
    });
  });

  it('resolves an object-mode commit by shifting every anchor with the candle-index/price delta', () => {
    const interaction = useKlineDrawingInteraction();
    const drawing = buildDrawing();

    interaction.beginBodyDrag(drawing, { time: '2026-03-18', price: 530 });
    const commit = interaction.resolveDragCommit(drawing, { time: '2026-03-19', price: 535 }, candles);

    expect(commit).toEqual({
      type: 'move',
      drawingId: 'trend-1',
      anchors: [
        { time: '2026-03-19', price: 538.2 },
        { time: '2026-03-20', price: 555.5 },
      ],
    });
  });

  it('refuses to resolve a commit when there is no active drag, no anchor, or the drawing is locked/non-editable', () => {
    const interaction = useKlineDrawingInteraction();
    const drawing = buildDrawing();

    // 未开始拖拽。
    expect(interaction.resolveDragCommit(drawing, { time: '2026-03-19', price: 535 }, candles)).toBeNull();

    interaction.beginBodyDrag(drawing, { time: '2026-03-18', price: 530 });

    // 落点锚点为空。
    expect(interaction.resolveDragCommit(drawing, null, candles)).toBeNull();

    // 目标绘图对象为空。
    expect(interaction.resolveDragCommit(null, { time: '2026-03-19', price: 535 }, candles)).toBeNull();

    // 提交时绘图对象已被锁定(即便开始拖拽时未锁定)。
    expect(
      interaction.resolveDragCommit(buildDrawing({ locked: true }), { time: '2026-03-19', price: 535 }, candles),
    ).toBeNull();
  });
});
