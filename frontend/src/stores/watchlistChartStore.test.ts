import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@vue/devtools-api', () => ({
  setupDevtoolsPlugin: () => undefined,
}));

describe('watchlistChartStore', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
      },
      configurable: true,
    });
  });

  it('supports multi-selection, undo/redo, and group actions', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { useWatchlistChartStore } = await import('./watchlistChartStore');
    const store = useWatchlistChartStore();
    const symbol = '0700.HK';

    store.drawingsBySymbol[symbol] = [
      {
        id: 'drawing-1',
        symbol,
        toolType: 'trend_line',
        createdAt: '2026-03-28T00:00:00.000Z',
        updatedAt: '2026-03-28T00:00:00.000Z',
        locked: false,
        visible: true,
        style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
        anchors: [
          { time: '2026-03-18', price: 533.2 },
          { time: '2026-03-19', price: 550.5 },
        ],
        payload: {},
      },
      {
        id: 'drawing-2',
        symbol,
        toolType: 'horizontal_line',
        createdAt: '2026-03-28T00:00:00.000Z',
        updatedAt: '2026-03-28T00:00:00.000Z',
        locked: false,
        visible: true,
        style: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
        anchors: [{ time: '2026-03-18', price: 540 }],
        payload: {},
      },
    ];

    store.selectDrawing('drawing-1');
    expect(store.selectedDrawingIds).toEqual(['drawing-1']);

    store.selectDrawing('drawing-2', { append: true });
    expect(store.selectedDrawingIds).toEqual(['drawing-1', 'drawing-2']);
    expect(store.selectedDrawingId).toBe('drawing-1');

    store.toggleSelectedLocked(symbol);
    expect(store.drawingsBySymbol[symbol].every((drawing) => drawing.locked)).toBe(true);
    expect(store.canUndo(symbol)).toBe(true);

    store.undo(symbol);
    expect(store.drawingsBySymbol[symbol].every((drawing) => drawing.locked === false)).toBe(true);
    expect(store.canRedo(symbol)).toBe(true);

    store.redo(symbol);
    expect(store.drawingsBySymbol[symbol].every((drawing) => drawing.locked)).toBe(true);

    store.duplicateSelectedDrawings(symbol);
    expect(store.drawingsBySymbol[symbol]).toHaveLength(4);

    store.deleteSelectedDrawings(symbol);
    expect(store.drawingsBySymbol[symbol]).toHaveLength(2);

    store.undo(symbol);
    expect(store.drawingsBySymbol[symbol]).toHaveLength(4);

    store.updateDrawingStyle(symbol, 'drawing-1', { color: '#fb7185' });
    expect(store.canRedo(symbol)).toBe(false);
  });
});
