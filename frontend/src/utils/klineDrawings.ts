import type {
  KlineDrawing,
  KlineDrawingAnchor,
  KlineDrawingPayload,
  KlineDrawingStyle,
  KlineDrawingTool,
  VersionedPersistedValue,
} from '../types/api';

const STORAGE_VERSION = 1;

const TOOL_DEFAULT_STYLE: Record<Exclude<KlineDrawingTool, 'select'>, KlineDrawingStyle> = {
  trend_line: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
  horizontal_line: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
  price_range: { color: '#34d399', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.16 },
  fibonacci_retracement: { color: '#c084fc', lineWidth: 1, lineStyle: 'solid', fillOpacity: 0.12 },
  price_note: { color: '#fb7185', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0 },
};

function nowIso() {
  return new Date().toISOString();
}

export function drawingStorageKey(symbol: string) {
  return `news-caught:kline-drawings:${symbol}`;
}

export function createDrawingId() {
  return `drawing-${Math.random().toString(36).slice(2, 10)}`;
}

export function getDefaultDrawingStyle(toolType: Exclude<KlineDrawingTool, 'select'>): KlineDrawingStyle {
  return { ...TOOL_DEFAULT_STYLE[toolType] };
}

export function getDefaultPriceNoteText(anchor: KlineDrawingAnchor) {
  return anchor.price.toFixed(2);
}

export function createDrawing(
  symbol: string,
  toolType: Exclude<KlineDrawingTool, 'select'>,
  anchors: KlineDrawingAnchor[],
  payload: KlineDrawingPayload = {},
): KlineDrawing {
  const normalizedPayload =
    toolType === 'price_note'
      ? { text: payload.text?.trim() || getDefaultPriceNoteText(anchors[0] ?? { time: '', price: 0 }) }
      : {};

  return {
    id: createDrawingId(),
    symbol,
    toolType,
    createdAt: nowIso(),
    updatedAt: nowIso(),
    locked: false,
    visible: true,
    style: getDefaultDrawingStyle(toolType),
    anchors,
    payload: normalizedPayload,
  };
}

export function updateDrawing(drawing: KlineDrawing, patch: Partial<KlineDrawing>): KlineDrawing {
  return {
    ...drawing,
    ...patch,
    updatedAt: nowIso(),
  };
}

export function moveDrawingAnchors(drawing: KlineDrawing, anchors: KlineDrawingAnchor[]) {
  return updateDrawing(drawing, { anchors });
}

export function persistDrawingsPayload(drawings: KlineDrawing[]): VersionedPersistedValue<KlineDrawing[]> {
  return {
    version: STORAGE_VERSION,
    savedAt: nowIso(),
    payload: drawings,
  };
}

export function normalizeDrawing(input: unknown, symbol: string): KlineDrawing | null {
  if (!input || typeof input !== 'object') {
    return null;
  }
  const value = input as Record<string, unknown>;
  const toolType = value.toolType;
  const anchors = Array.isArray(value.anchors) ? (value.anchors as KlineDrawingAnchor[]) : [];
  if (
    toolType !== 'trend_line' &&
    toolType !== 'horizontal_line' &&
    toolType !== 'price_range' &&
    toolType !== 'fibonacci_retracement' &&
    toolType !== 'price_note'
  ) {
    return null;
  }
  if (!anchors.length) {
    return null;
  }
  const payload = (value.payload as KlineDrawingPayload | undefined) ?? {};
  return {
    id: typeof value.id === 'string' ? value.id : createDrawingId(),
    symbol,
    toolType,
    createdAt: typeof value.createdAt === 'string' ? value.createdAt : nowIso(),
    updatedAt: typeof value.updatedAt === 'string' ? value.updatedAt : nowIso(),
    locked: Boolean(value.locked),
    visible: value.visible !== false,
    style: {
      ...getDefaultDrawingStyle(toolType),
      ...(typeof value.style === 'object' && value.style ? (value.style as Partial<KlineDrawingStyle>) : {}),
    },
    anchors,
    payload:
      toolType === 'price_note'
        ? { text: payload.text?.trim() || getDefaultPriceNoteText(anchors[0]) }
        : {},
  };
}

export function restoreDrawings(raw: string | null, symbol: string): KlineDrawing[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as VersionedPersistedValue<unknown> | unknown[];
    const payload = Array.isArray(parsed) ? parsed : Array.isArray(parsed.payload) ? parsed.payload : [];
    return payload
      .map((item) => normalizeDrawing(item, symbol))
      .filter((item): item is KlineDrawing => item !== null);
  } catch {
    return [];
  }
}

export function serializeDrawings(drawings: KlineDrawing[]) {
  return JSON.stringify(persistDrawingsPayload(drawings));
}

const EDITABLE_TOOL_TYPES: ReadonlySet<KlineDrawing['toolType']> = new Set([
  'trend_line',
  'horizontal_line',
  'price_range',
  'fibonacci_retracement',
  'price_note',
]);

export function isEditableDrawing(drawing: KlineDrawing | null): boolean {
  return Boolean(drawing && EDITABLE_TOOL_TYPES.has(drawing.toolType));
}

export function isDrawingDraggable(drawing: KlineDrawing | null): boolean {
  return Boolean(drawing && !drawing.locked && isEditableDrawing(drawing));
}

export function resolveLabelEditorText(drawing: KlineDrawing): string {
  return drawing.payload.text ?? drawing.anchors[0]?.price.toFixed(2) ?? '';
}
