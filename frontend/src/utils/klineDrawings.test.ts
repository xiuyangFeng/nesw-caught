import { describe, expect, it } from 'vitest';

import type { KlineDrawing } from '../types/api';
import { isDrawingDraggable, isEditableDrawing, resolveLabelEditorText } from './klineDrawings';

function buildDrawing(overrides: Partial<KlineDrawing> = {}): KlineDrawing {
  return {
    id: 'drawing-1',
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

describe('klineDrawings interaction helpers', () => {
  it('treats all known drawing tool types as editable and rejects null', () => {
    expect(isEditableDrawing(null)).toBe(false);
    expect(isEditableDrawing(buildDrawing({ toolType: 'trend_line' }))).toBe(true);
    expect(isEditableDrawing(buildDrawing({ toolType: 'horizontal_line' }))).toBe(true);
    expect(isEditableDrawing(buildDrawing({ toolType: 'price_range' }))).toBe(true);
    expect(isEditableDrawing(buildDrawing({ toolType: 'fibonacci_retracement' }))).toBe(true);
    expect(isEditableDrawing(buildDrawing({ toolType: 'price_note' }))).toBe(true);
  });

  it('only allows dragging editable and unlocked drawings', () => {
    expect(isDrawingDraggable(null)).toBe(false);
    expect(isDrawingDraggable(buildDrawing({ locked: false }))).toBe(true);
    expect(isDrawingDraggable(buildDrawing({ locked: true }))).toBe(false);
  });

  it('resolves the price-note editor seed text with the same precedence as the original inline expression', () => {
    // 显式文案优先(即便是空串,?? 也不会回退到价格文案)。
    expect(resolveLabelEditorText(buildDrawing({ toolType: 'price_note', payload: { text: '观察位' } }))).toBe('观察位');
    expect(resolveLabelEditorText(buildDrawing({ toolType: 'price_note', payload: { text: '' } }))).toBe('');

    // 无文案时回退到首个锚点价格的两位小数格式。
    expect(
      resolveLabelEditorText(
        buildDrawing({ toolType: 'price_note', payload: {}, anchors: [{ time: '2026-03-18', price: 545 }] }),
      ),
    ).toBe('545.00');

    // 无锚点也无文案时回退为空串。
    expect(resolveLabelEditorText(buildDrawing({ toolType: 'price_note', payload: {}, anchors: [] }))).toBe('');
  });
});
