import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import type {
  KlineCandle,
  KlineDrawing,
  KlineDrawingAnchor,
  KlineDrawingStyle,
  KlineDrawingTool,
  KlineIndicatorTemplate,
  KlineSubIndicator,
} from '../types/api';
import {
  createDrawing,
  createDrawingId,
  drawingStorageKey,
  restoreDrawings,
  serializeDrawings,
  updateDrawing,
} from '../utils/klineDrawings';
import { moveDrawingByDelta } from '../utils/klineOverlayGeometry';
import {
  ACTIVE_TEMPLATE_STORAGE_KEY,
  cloneTemplate,
  DEFAULT_TEMPLATE_ID,
  resolveActiveTemplateId,
  resolveTemplateSet,
  serializeTemplateSet,
} from '../utils/klineIndicatorTemplates';

export const useWatchlistChartStore = defineStore('watchlistChartStore', () => {
  const activeTool = ref<KlineDrawingTool>('select');
  const selectedDrawingId = ref<string | null>(null);
  const selectedDrawingIds = ref<string[]>([]);
  const safeStorage = (() => {
    try {
      return globalThis.localStorage;
    } catch {
      return null;
    }
  })();
  const templates = ref<KlineIndicatorTemplate[]>(resolveTemplateSet(safeStorage?.getItem?.('news-caught:kline-indicator-templates') ?? null));
  const activeTemplateId = ref<string>(resolveActiveTemplateId(safeStorage?.getItem?.(ACTIVE_TEMPLATE_STORAGE_KEY) ?? null, templates.value));
  const subIndicator = ref<KlineSubIndicator>('VOL');
  const drawingsBySymbol = ref<Record<string, KlineDrawing[]>>({});
  const draft = ref<{
    toolType: Exclude<KlineDrawingTool, 'select'>;
    anchors: KlineDrawingAnchor[];
  } | null>(null);
  const historyPastBySymbol = ref<Record<string, KlineDrawing[][]>>({});
  const historyFutureBySymbol = ref<Record<string, KlineDrawing[][]>>({});

  let persistHandle: ReturnType<typeof setTimeout> | null = null;

  const activeTemplate = computed(
    () => templates.value.find((template) => template.id === activeTemplateId.value) ?? templates.value.find((template) => template.id === DEFAULT_TEMPLATE_ID) ?? null,
  );

  function schedulePersist(symbol: string) {
    if (persistHandle) {
      clearTimeout(persistHandle);
    }
    persistHandle = setTimeout(() => flushSymbol(symbol), 150);
  }

  function flushSymbol(symbol: string) {
    const drawings = drawingsBySymbol.value[symbol] ?? [];
    safeStorage?.setItem?.(drawingStorageKey(symbol), serializeDrawings(drawings));
  }

  function persistTemplates() {
    safeStorage?.setItem?.('news-caught:kline-indicator-templates', serializeTemplateSet(templates.value));
    safeStorage?.setItem?.(ACTIVE_TEMPLATE_STORAGE_KEY, activeTemplateId.value);
  }

  function hydrateForSymbol(symbol: string, candles: KlineCandle[]) {
    if (!drawingsBySymbol.value[symbol]) {
      drawingsBySymbol.value[symbol] = restoreDrawings(safeStorage?.getItem?.(drawingStorageKey(symbol)) ?? null, symbol);
    }
    if (!candles.length) {
      activeTool.value = 'select';
      draft.value = null;
      clearSelection();
    }
  }

  function cloneDrawings(drawings: KlineDrawing[]) {
    return drawings.map((drawing) => ({
      ...drawing,
      style: { ...drawing.style },
      anchors: drawing.anchors.map((anchor) => ({ ...anchor })),
      payload: { ...drawing.payload },
    }));
  }

  function pushHistory(symbol: string) {
    const current = cloneDrawings(drawingsBySymbol.value[symbol] ?? []);
    historyPastBySymbol.value[symbol] = [...(historyPastBySymbol.value[symbol] ?? []), current];
    historyFutureBySymbol.value[symbol] = [];
  }

  function canUndo(symbol: string) {
    return (historyPastBySymbol.value[symbol]?.length ?? 0) > 0;
  }

  function canRedo(symbol: string) {
    return (historyFutureBySymbol.value[symbol]?.length ?? 0) > 0;
  }

  function restoreSnapshot(symbol: string, snapshot: KlineDrawing[]) {
    drawingsBySymbol.value[symbol] = cloneDrawings(snapshot);
    const availableIds = new Set(drawingsBySymbol.value[symbol].map((drawing) => drawing.id));
    selectedDrawingIds.value = selectedDrawingIds.value.filter((id) => availableIds.has(id));
    selectedDrawingId.value = selectedDrawingIds.value[0] ?? null;
    schedulePersist(symbol);
  }

  function undo(symbol: string) {
    const past = historyPastBySymbol.value[symbol] ?? [];
    if (!past.length) {
      return;
    }
    const current = cloneDrawings(drawingsBySymbol.value[symbol] ?? []);
    const snapshot = past[past.length - 1];
    historyPastBySymbol.value[symbol] = past.slice(0, -1);
    historyFutureBySymbol.value[symbol] = [...(historyFutureBySymbol.value[symbol] ?? []), current];
    restoreSnapshot(symbol, snapshot);
  }

  function redo(symbol: string) {
    const future = historyFutureBySymbol.value[symbol] ?? [];
    if (!future.length) {
      return;
    }
    const current = cloneDrawings(drawingsBySymbol.value[symbol] ?? []);
    const snapshot = future[future.length - 1];
    historyFutureBySymbol.value[symbol] = future.slice(0, -1);
    historyPastBySymbol.value[symbol] = [...(historyPastBySymbol.value[symbol] ?? []), current];
    restoreSnapshot(symbol, snapshot);
  }

  function selectTool(tool: KlineDrawingTool) {
    activeTool.value = tool;
    if (tool === 'select') {
      draft.value = null;
    }
  }

  function startDraft(anchor: KlineDrawingAnchor) {
    if (activeTool.value === 'select') {
      return;
    }
    if (!draft.value || draft.value.toolType !== activeTool.value) {
      draft.value = { toolType: activeTool.value, anchors: [anchor] };
      return;
    }
    draft.value.anchors = [...draft.value.anchors, anchor];
  }

  function updateDraft(anchor: KlineDrawingAnchor) {
    if (!draft.value) {
      return;
    }
    if (draft.value.anchors.length === 1) {
      draft.value.anchors = [draft.value.anchors[0], anchor];
      return;
    }
    draft.value.anchors[draft.value.anchors.length - 1] = anchor;
  }

  function commitDraft(symbol: string) {
    if (!draft.value) {
      return;
    }
    pushHistory(symbol);
    const drawing = createDrawing(symbol, draft.value.toolType, draft.value.anchors);
    drawingsBySymbol.value[symbol] = [...(drawingsBySymbol.value[symbol] ?? []), drawing];
    selectedDrawingIds.value = [drawing.id];
    selectedDrawingId.value = drawing.id;
    draft.value = null;
    activeTool.value = 'select';
    schedulePersist(symbol);
  }

  function cancelDraft() {
    draft.value = null;
    activeTool.value = 'select';
  }

  function clearSelection() {
    selectedDrawingId.value = null;
    selectedDrawingIds.value = [];
  }

  function resolveSelectedDrawings(symbol: string) {
    if (!selectedDrawingIds.value.length) {
      return [];
    }
    const selected = new Set(selectedDrawingIds.value);
    return (drawingsBySymbol.value[symbol] ?? []).filter((drawing) => selected.has(drawing.id));
  }

  function selectDrawing(id: string | null, options?: { append?: boolean }) {
    if (!id) {
      clearSelection();
      return;
    }
    if (options?.append) {
      selectedDrawingIds.value = selectedDrawingIds.value.includes(id)
        ? selectedDrawingIds.value.filter((item) => item !== id)
        : [...selectedDrawingIds.value, id];
      selectedDrawingId.value = selectedDrawingIds.value[0] ?? null;
      return;
    }
    selectedDrawingIds.value = [id];
    selectedDrawingId.value = id;
  }

  function findDrawing(symbol: string, id: string) {
    return drawingsBySymbol.value[symbol]?.find((drawing) => drawing.id === id) ?? null;
  }

  function patchDrawing(symbol: string, id: string, updater: (drawing: KlineDrawing) => KlineDrawing | null) {
    const current = drawingsBySymbol.value[symbol] ?? [];
    pushHistory(symbol);
    drawingsBySymbol.value[symbol] = current
      .map((drawing) => (drawing.id === id ? updater(drawing) : drawing))
      .filter((drawing): drawing is KlineDrawing => drawing !== null);
    const availableIds = new Set(drawingsBySymbol.value[symbol].map((drawing) => drawing.id));
    selectedDrawingIds.value = selectedDrawingIds.value.filter((drawingId) => availableIds.has(drawingId));
    selectedDrawingId.value = selectedDrawingIds.value[0] ?? null;
    schedulePersist(symbol);
  }

  function updateDrawingAnchors(symbol: string, id: string, anchors: KlineDrawingAnchor[]) {
    patchDrawing(symbol, id, (drawing) => updateDrawing(drawing, { anchors }));
  }

  function updateDrawingStyle(symbol: string, id: string, stylePatch: Partial<KlineDrawingStyle>) {
    patchDrawing(symbol, id, (drawing) => updateDrawing(drawing, { style: { ...drawing.style, ...stylePatch } }));
  }

  function moveDrawing(symbol: string, id: string, anchors: KlineDrawingAnchor[]) {
    updateDrawingAnchors(symbol, id, anchors);
  }

  function commitLabelEdit(symbol: string, id: string, text: string) {
    patchDrawing(symbol, id, (drawing) =>
      updateDrawing(drawing, { payload: { text: text.trim() || drawing.payload.text || drawing.anchors[0]?.price.toFixed(2) } }),
    );
  }

  function deleteDrawing(symbol: string, id: string) {
    patchDrawing(symbol, id, () => null);
  }

  function clearSymbolDrawings(symbol: string) {
    pushHistory(symbol);
    drawingsBySymbol.value[symbol] = [];
    clearSelection();
    schedulePersist(symbol);
  }

  function toggleDrawingLocked(symbol: string, id: string) {
    patchDrawing(symbol, id, (drawing) => updateDrawing(drawing, { locked: !drawing.locked }));
  }

  function toggleDrawingVisible(symbol: string, id: string) {
    patchDrawing(symbol, id, (drawing) => updateDrawing(drawing, { visible: !drawing.visible }));
  }

  function applyTemplate(templateId: string) {
    activeTemplateId.value = templates.value.some((template) => template.id === templateId) ? templateId : DEFAULT_TEMPLATE_ID;
    subIndicator.value = activeTemplate.value?.subIndicator ?? 'VOL';
    persistTemplates();
  }

  function saveCustomTemplate(templateInput: KlineIndicatorTemplate) {
    const existingIndex = templates.value.findIndex((template) => template.id === templateInput.id && template.source === 'custom');
    if (existingIndex >= 0) {
      templates.value[existingIndex] = { ...templateInput, source: 'custom' };
    } else {
      templates.value = [...templates.value, { ...templateInput, source: 'custom' }];
    }
    activeTemplateId.value = templateInput.id;
    persistTemplates();
  }

  function copyActiveTemplate() {
    if (!activeTemplate.value) {
      return null;
    }
    const clone = cloneTemplate(activeTemplate.value);
    saveCustomTemplate(clone);
    return clone;
  }

  function deleteCustomTemplate(templateId: string) {
    templates.value = templates.value.filter((template) => template.id !== templateId || template.source === 'preset');
    if (!templates.value.some((template) => template.id === activeTemplateId.value)) {
      activeTemplateId.value = DEFAULT_TEMPLATE_ID;
    }
    persistTemplates();
  }

  function setSubIndicator(indicator: KlineSubIndicator) {
    subIndicator.value = indicator;
  }

  function deleteSelectedDrawings(symbol: string) {
    const validSelectedDrawings = resolveSelectedDrawings(symbol);
    if (!validSelectedDrawings.length) {
      return;
    }
    pushHistory(symbol);
    const selected = new Set(selectedDrawingIds.value);
    drawingsBySymbol.value[symbol] = (drawingsBySymbol.value[symbol] ?? []).filter((drawing) => !selected.has(drawing.id));
    clearSelection();
    schedulePersist(symbol);
  }

  function nudgeSelectedDrawings(
    symbol: string,
    input: {
      candles: KlineCandle[];
      timeStep: number;
      priceDelta: number;
    },
  ) {
    const drawings = drawingsBySymbol.value[symbol] ?? [];
    const selected = new Set(selectedDrawingIds.value);
    const validSelectedDrawings = resolveSelectedDrawings(symbol);
    if (!validSelectedDrawings.length) {
      return;
    }
    const nextDrawings = drawings.map((drawing) =>
      selected.has(drawing.id)
        ? updateDrawing(drawing, {
            anchors: moveDrawingByDelta(drawing, input.candles, input.timeStep, input.priceDelta),
          })
        : drawing,
    );
    const changed = nextDrawings.some((drawing, index) =>
      drawing.anchors.some(
        (anchor, anchorIndex) =>
          anchor.time !== drawings[index]?.anchors[anchorIndex]?.time || anchor.price !== drawings[index]?.anchors[anchorIndex]?.price,
      ),
    );
    if (!changed) {
      return;
    }
    pushHistory(symbol);
    drawingsBySymbol.value[symbol] = nextDrawings;
    const availableIds = new Set(drawingsBySymbol.value[symbol].map((drawing) => drawing.id));
    selectedDrawingIds.value = selectedDrawingIds.value.filter((id) => availableIds.has(id));
    selectedDrawingId.value = selectedDrawingIds.value[0] ?? null;
    schedulePersist(symbol);
  }

  function duplicateSelectedDrawings(symbol: string) {
    if (!selectedDrawingIds.value.length) {
      return;
    }
    const current = drawingsBySymbol.value[symbol] ?? [];
    const selected = current.filter((drawing) => selectedDrawingIds.value.includes(drawing.id));
    if (!selected.length) {
      return;
    }
    pushHistory(symbol);
    const now = new Date().toISOString();
    const clones = selected.map((drawing) => ({
      ...drawing,
      id: createDrawingId(),
      createdAt: now,
      updatedAt: now,
      style: { ...drawing.style },
      anchors: drawing.anchors.map((anchor) => ({ ...anchor })),
      payload: { ...drawing.payload },
    }));
    drawingsBySymbol.value[symbol] = [...current, ...clones];
    selectedDrawingIds.value = clones.map((drawing) => drawing.id);
    selectedDrawingId.value = selectedDrawingIds.value[0] ?? null;
    schedulePersist(symbol);
  }

  function toggleSelectedLocked(symbol: string) {
    const validSelectedDrawings = resolveSelectedDrawings(symbol);
    if (!validSelectedDrawings.length) {
      return;
    }
    const selected = new Set(selectedDrawingIds.value);
    const drawings = drawingsBySymbol.value[symbol] ?? [];
    const shouldLock = drawings.some((drawing) => selected.has(drawing.id) && !drawing.locked);
    pushHistory(symbol);
    drawingsBySymbol.value[symbol] = drawings.map((drawing) =>
      selected.has(drawing.id) ? updateDrawing(drawing, { locked: shouldLock }) : drawing,
    );
    schedulePersist(symbol);
  }

  function toggleSelectedVisible(symbol: string) {
    const validSelectedDrawings = resolveSelectedDrawings(symbol);
    if (!validSelectedDrawings.length) {
      return;
    }
    const selected = new Set(selectedDrawingIds.value);
    const drawings = drawingsBySymbol.value[symbol] ?? [];
    const shouldShow = drawings.some((drawing) => selected.has(drawing.id) && !drawing.visible);
    pushHistory(symbol);
    drawingsBySymbol.value[symbol] = drawings.map((drawing) =>
      selected.has(drawing.id) ? updateDrawing(drawing, { visible: shouldShow }) : drawing,
    );
    schedulePersist(symbol);
  }

  function flushAll() {
    Object.keys(drawingsBySymbol.value).forEach(flushSymbol);
    persistTemplates();
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', flushAll);
  }

  return {
    activeTool,
    selectedDrawingId,
    selectedDrawingIds,
    templates,
    activeTemplateId,
    activeTemplate,
    drawingsBySymbol,
    draft,
    subIndicator,
    hydrateForSymbol,
    selectTool,
    startDraft,
    updateDraft,
    commitDraft,
    cancelDraft,
    selectDrawing,
    clearSelection,
    findDrawing,
    canUndo,
    canRedo,
    undo,
    redo,
    updateDrawingAnchors,
    updateDrawingStyle,
    moveDrawing,
    commitLabelEdit,
    deleteDrawing,
    clearSymbolDrawings,
    toggleDrawingLocked,
    toggleDrawingVisible,
    applyTemplate,
    saveCustomTemplate,
    copyActiveTemplate,
    deleteCustomTemplate,
    setSubIndicator,
    deleteSelectedDrawings,
    nudgeSelectedDrawings,
    duplicateSelectedDrawings,
    toggleSelectedLocked,
    toggleSelectedVisible,
    flushAll,
  };
});
