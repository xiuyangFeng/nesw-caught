import type {
  KlineIndicatorTemplate,
  KlineOverlayIndicator,
  VersionedPersistedValue,
} from '../types/api';

const TEMPLATE_VERSION = 1;
export const DEFAULT_TEMPLATE_ID = 'preset-classic';
export const TEMPLATE_STORAGE_KEY = 'news-caught:kline-indicator-templates';
export const ACTIVE_TEMPLATE_STORAGE_KEY = 'news-caught:kline-active-indicator-template';

function nowIso() {
  return new Date().toISOString();
}

function cloneOverlayIndicators(indicators: KlineOverlayIndicator[]) {
  return indicators.map((indicator) => ({
    ...indicator,
    params: { ...indicator.params },
  })) as KlineOverlayIndicator[];
}

export const PRESET_TEMPLATES: KlineIndicatorTemplate[] = [
  {
    id: DEFAULT_TEMPLATE_ID,
    name: '经典均线',
    scope: 'global',
    source: 'preset',
    version: TEMPLATE_VERSION,
    overlayIndicators: [
      { kind: 'MA', visible: true, params: { periods: [5, 10, 20, 60] } },
      { kind: 'BOLL', visible: true, params: { period: 20, stdDev: 2 } },
    ],
    subIndicator: 'VOL',
  },
  {
    id: 'preset-trend',
    name: '趋势跟随',
    scope: 'global',
    source: 'preset',
    version: TEMPLATE_VERSION,
    overlayIndicators: [
      { kind: 'EMA', visible: true, params: { periods: [12, 26] } },
      { kind: 'BOLL', visible: true, params: { period: 20, stdDev: 2 } },
    ],
    subIndicator: 'MACD',
  },
  {
    id: 'preset-range',
    name: '震荡观察',
    scope: 'global',
    source: 'preset',
    version: TEMPLATE_VERSION,
    overlayIndicators: [
      { kind: 'MA', visible: true, params: { periods: [20] } },
      { kind: 'BOLL', visible: true, params: { period: 20, stdDev: 2 } },
    ],
    subIndicator: 'KDJ',
  },
  {
    id: 'preset-strength',
    name: '强弱判断',
    scope: 'global',
    source: 'preset',
    version: TEMPLATE_VERSION,
    overlayIndicators: [{ kind: 'EMA', visible: true, params: { periods: [12, 26] } }],
    subIndicator: 'RSI',
  },
];

function sanitizePeriods(periods: number[], maxItems: number) {
  const deduped = [...new Set(periods.filter((item) => Number.isFinite(item) && item >= 2 && item <= 250))];
  return deduped.sort((left, right) => left - right).slice(0, maxItems);
}

export function normalizeTemplate(input: unknown): KlineIndicatorTemplate | null {
  if (!input || typeof input !== 'object') {
    return null;
  }
  const value = input as Record<string, unknown>;
  const rawIndicators = Array.isArray(value.overlayIndicators) ? value.overlayIndicators : [];
  const indicators: KlineOverlayIndicator[] = [];
  for (const rawIndicator of rawIndicators) {
    if (!rawIndicator || typeof rawIndicator !== 'object') {
      continue;
    }
    const indicator = rawIndicator as Record<string, unknown>;
    if (indicator.kind === 'MA') {
      const periods = sanitizePeriods(((indicator.params as { periods?: number[] } | undefined)?.periods ?? []), 6);
      if (!periods.length) {
        continue;
      }
      indicators.push({ kind: 'MA', visible: indicator.visible !== false, params: { periods } });
      continue;
    }
    if (indicator.kind === 'EMA') {
      const periods = sanitizePeriods(((indicator.params as { periods?: number[] } | undefined)?.periods ?? []), 4);
      if (!periods.length) {
        continue;
      }
      indicators.push({ kind: 'EMA', visible: indicator.visible !== false, params: { periods } });
      continue;
    }
    if (indicator.kind === 'BOLL') {
      const period = Number((indicator.params as { period?: number } | undefined)?.period ?? 20);
      const stdDev = Number((indicator.params as { stdDev?: number } | undefined)?.stdDev ?? 2);
      if (period < 5 || period > 250 || stdDev < 1 || stdDev > 4) {
        continue;
      }
      indicators.push({ kind: 'BOLL', visible: indicator.visible !== false, params: { period, stdDev } });
    }
  }
  const subIndicator = value.subIndicator;
  if (subIndicator !== 'VOL' && subIndicator !== 'MACD' && subIndicator !== 'KDJ' && subIndicator !== 'RSI') {
    return null;
  }
  if (!indicators.length) {
    return null;
  }
  return {
    id: typeof value.id === 'string' ? value.id : `template-${Math.random().toString(36).slice(2, 10)}`,
    name: typeof value.name === 'string' && value.name.trim() ? value.name.trim() : '未命名模板',
    scope: 'global',
    source: value.source === 'preset' ? 'preset' : 'custom',
    version: TEMPLATE_VERSION,
    overlayIndicators: indicators,
    subIndicator,
  };
}

export function cloneTemplate(template: KlineIndicatorTemplate, name = `${template.name}-副本`): KlineIndicatorTemplate {
  return {
    ...template,
    id: `template-${Math.random().toString(36).slice(2, 10)}`,
    name,
    source: 'custom',
    overlayIndicators: cloneOverlayIndicators(template.overlayIndicators),
  };
}

export function resolveTemplateSet(raw: string | null) {
  const presets = PRESET_TEMPLATES.map((template) => ({
    ...template,
    overlayIndicators: cloneOverlayIndicators(template.overlayIndicators),
  }));
  if (!raw) {
    return presets;
  }
  try {
    const parsed = JSON.parse(raw) as VersionedPersistedValue<unknown> | unknown[];
    const payload = Array.isArray(parsed) ? parsed : Array.isArray(parsed.payload) ? parsed.payload : [];
    const customTemplates = payload
      .map((item) => normalizeTemplate(item))
      .filter((item): item is KlineIndicatorTemplate => item !== null && item.source !== 'preset');
    return [...presets, ...customTemplates];
  } catch {
    return presets;
  }
}

export function serializeTemplateSet(templates: KlineIndicatorTemplate[]) {
  const customTemplates = templates.filter((template) => template.source === 'custom');
  return JSON.stringify({
    version: TEMPLATE_VERSION,
    savedAt: nowIso(),
    payload: customTemplates,
  } satisfies VersionedPersistedValue<KlineIndicatorTemplate[]>);
}

export function resolveActiveTemplateId(raw: string | null, templates: KlineIndicatorTemplate[]) {
  const candidate = raw ?? DEFAULT_TEMPLATE_ID;
  return templates.some((template) => template.id === candidate) ? candidate : DEFAULT_TEMPLATE_ID;
}
