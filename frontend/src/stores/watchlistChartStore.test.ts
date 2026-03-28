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

  async function createStore() {
    const { createPinia, setActivePinia } = await import('pinia');
    setActivePinia(createPinia());
    const { useWatchlistChartStore } = await import('./watchlistChartStore');
    return useWatchlistChartStore();
  }

  function seedDrawings(store: Awaited<ReturnType<typeof createStore>>, symbol: string) {
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
  }

  it('supports multi-selection, undo/redo, and group actions', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

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

  it('clears multi-selection when deleting selected drawings', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

    store.selectDrawing('drawing-1');
    store.selectDrawing('drawing-2', { append: true });

    store.deleteSelectedDrawings(symbol);

    expect(store.drawingsBySymbol[symbol]).toHaveLength(0);
    expect(store.selectedDrawingIds).toEqual([]);
    expect(store.selectedDrawingId).toBeNull();
  });

  it('nudges selected drawings and replays the move through undo/redo', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

    store.selectDrawing('drawing-1');
    store.selectDrawing('drawing-2', { append: true });

    store.nudgeSelectedDrawings(symbol, {
      candles: [
        { time: '2026-03-18', open: 530, high: 555, low: 528, close: 544, volume: 1000 },
        { time: '2026-03-19', open: 544, high: 560, low: 540, close: 552, volume: 1100 },
        { time: '2026-03-20', open: 552, high: 565, low: 548, close: 560, volume: 1200 },
      ],
      timeStep: 1,
      priceDelta: 7.5,
    });

    expect(store.drawingsBySymbol[symbol][0]?.anchors).toEqual([
      { time: '2026-03-19', price: 540.7 },
      { time: '2026-03-20', price: 558 },
    ]);
    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 547.5 }]);
    expect(store.selectedDrawingIds).toEqual(['drawing-1', 'drawing-2']);
    expect(store.canUndo(symbol)).toBe(true);

    store.undo(symbol);
    expect(store.drawingsBySymbol[symbol][0]?.anchors).toEqual([
      { time: '2026-03-18', price: 533.2 },
      { time: '2026-03-19', price: 550.5 },
    ]);
    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 540 }]);
    expect(store.canRedo(symbol)).toBe(true);

    store.redo(symbol);
    expect(store.drawingsBySymbol[symbol][0]?.anchors).toEqual([
      { time: '2026-03-19', price: 540.7 },
      { time: '2026-03-20', price: 558 },
    ]);
    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 547.5 }]);
  });

  it('keeps horizontal-line time fixed on left-right nudges', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

    store.selectDrawing('drawing-2');
    store.nudgeSelectedDrawings(symbol, {
      candles: [
        { time: '2026-03-18', open: 530, high: 555, low: 528, close: 544, volume: 1000 },
        { time: '2026-03-19', open: 544, high: 560, low: 540, close: 552, volume: 1100 },
        { time: '2026-03-20', open: 552, high: 565, low: 548, close: 560, volume: 1200 },
      ],
      timeStep: 1,
      priceDelta: 0,
    });

    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 540 }]);
  });

  it('does not create history for clamped or unsupported no-op nudges', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

    store.selectDrawing('drawing-2');
    store.nudgeSelectedDrawings(symbol, {
      candles: [
        { time: '2026-03-18', open: 530, high: 555, low: 528, close: 544, volume: 1000 },
        { time: '2026-03-19', open: 544, high: 560, low: 540, close: 552, volume: 1100 },
      ],
      timeStep: 1,
      priceDelta: 0,
    });

    expect(store.canUndo(symbol)).toBe(false);
    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 540 }]);
  });

  it('does nothing when the selected drawing ids are invalid', async () => {
    const store = await createStore();
    const symbol = '0700.HK';
    seedDrawings(store, symbol);

    store.selectDrawing('missing-drawing');
    store.nudgeSelectedDrawings(symbol, {
      candles: [
        { time: '2026-03-18', open: 530, high: 555, low: 528, close: 544, volume: 1000 },
      ],
      timeStep: 1,
      priceDelta: 7.5,
    });

    expect(store.drawingsBySymbol[symbol][0]?.anchors).toEqual([
      { time: '2026-03-18', price: 533.2 },
      { time: '2026-03-19', price: 550.5 },
    ]);
    expect(store.drawingsBySymbol[symbol][1]?.anchors).toEqual([{ time: '2026-03-18', price: 540 }]);
    expect(store.canUndo(symbol)).toBe(false);

    store.deleteSelectedDrawings(symbol);
    store.toggleSelectedLocked(symbol);
    store.toggleSelectedVisible(symbol);
    expect(store.drawingsBySymbol[symbol][0]?.locked).toBe(false);
    expect(store.drawingsBySymbol[symbol][0]?.visible).toBe(true);
    expect(store.canUndo(symbol)).toBe(false);
  });
});
