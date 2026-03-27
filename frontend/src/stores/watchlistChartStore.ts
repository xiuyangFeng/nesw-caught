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
  drawingStorageKey,
  restoreDrawings,
  serializeDrawings,
  updateDrawing,
} from '../utils/klineDrawings';
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
      selectedDrawingId.value = null;
    }
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
    const drawing = createDrawing(symbol, draft.value.toolType, draft.value.anchors);
    drawingsBySymbol.value[symbol] = [...(drawingsBySymbol.value[symbol] ?? []), drawing];
    selectedDrawingId.value = drawing.id;
    draft.value = null;
    activeTool.value = 'select';
    schedulePersist(symbol);
  }

  function cancelDraft() {
    draft.value = null;
    activeTool.value = 'select';
  }

  function selectDrawing(id: string | null) {
    selectedDrawingId.value = id;
  }

  function findDrawing(symbol: string, id: string) {
    return drawingsBySymbol.value[symbol]?.find((drawing) => drawing.id === id) ?? null;
  }

  function patchDrawing(symbol: string, id: string, updater: (drawing: KlineDrawing) => KlineDrawing | null) {
    const current = drawingsBySymbol.value[symbol] ?? [];
    drawingsBySymbol.value[symbol] = current
      .map((drawing) => (drawing.id === id ? updater(drawing) : drawing))
      .filter((drawing): drawing is KlineDrawing => drawing !== null);
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
    if (selectedDrawingId.value === id) {
      selectedDrawingId.value = null;
    }
  }

  function clearSymbolDrawings(symbol: string) {
    drawingsBySymbol.value[symbol] = [];
    selectedDrawingId.value = null;
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
    findDrawing,
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
    flushAll,
  };
});
