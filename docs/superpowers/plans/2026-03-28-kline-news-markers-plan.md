# K-line News Markers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show news events as colored markers on the K-line candlestick chart, with hover tooltips and click popups displaying news summaries.

**Architecture:** Backend already returns `news_events` aligned to trading days in the K-line API. We add a `summary` field to the response, then use lightweight-charts' native `setMarkers()` to render sentiment-colored circles below candles. A tooltip component appears on hover, a popup component on click.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Vue 3/TypeScript/lightweight-charts (frontend)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/schemas/market.py` | Modify | Add `summary` field to `NewsEventItemView` |
| `backend/app/services/market_chart_service.py` | Modify | Extract `summary` in `_align_news_events()` |
| `frontend/src/types/api.ts` | Modify | Add `summary` to `NewsEventMarkerItem` |
| `frontend/src/components/watchlist/KlineChart.vue` | Modify | Add marker rendering, tooltip/popup integration |
| `frontend/src/components/watchlist/KlineNewsTooltip.vue` | Create | Hover tooltip component |
| `frontend/src/components/watchlist/KlineNewsPopup.vue` | Create | Click popup component |

---

### Task 1: Backend — Add `summary` to K-line news events

**Files:**
- Modify: `backend/app/schemas/market.py:81-85`
- Modify: `backend/app/services/market_chart_service.py:216-224`

- [ ] **Step 1: Add `summary` field to `NewsEventItemView`**

In `backend/app/schemas/market.py`, change `NewsEventItemView`:

```python
class NewsEventItemView(BaseModel):
    id: int
    title: str
    sentiment: str
    summary: str = ""
```

- [ ] **Step 2: Extract `summary` in `_align_news_events()`**

In `backend/app/services/market_chart_service.py`, in the `_align_news_events` method, add `summary` to the dict at line ~220 (inside `grouped.setdefault(anchor, []).append(...)`):

Change:
```python
                {
                    "id": int(getattr(item, "id", None) if not isinstance(item, dict) else item.get("id")),
                    "title": str(getattr(item, "title", "") if not isinstance(item, dict) else item.get("title", "")),
                    "sentiment": str(
                        getattr(item, "sentiment_label", "unknown") if not isinstance(item, dict) else item.get("sentiment_label", "unknown")
                    ),
                }
```

To:
```python
                {
                    "id": int(getattr(item, "id", None) if not isinstance(item, dict) else item.get("id")),
                    "title": str(getattr(item, "title", "") if not isinstance(item, dict) else item.get("title", "")),
                    "sentiment": str(
                        getattr(item, "sentiment_label", "unknown") if not isinstance(item, dict) else item.get("sentiment_label", "unknown")
                    ),
                    "summary": str(getattr(item, "summary", "") or "" if not isinstance(item, dict) else (item.get("summary") or "")),
                }
```

- [ ] **Step 3: Run backend tests**

Run: `conda run -n news-caught pytest backend/tests -v`
Expected: All existing tests pass (no behavior change for existing fields)

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/market.py backend/app/services/market_chart_service.py
git commit -m "feat(kline): add summary to news event items in kline API"
```

---

### Task 2: Frontend types — Add `summary` to `NewsEventMarkerItem`

**Files:**
- Modify: `frontend/src/types/api.ts:321-325`

- [ ] **Step 1: Update `NewsEventMarkerItem` type**

In `frontend/src/types/api.ts`, change:

```typescript
export interface NewsEventMarkerItem {
  id: number;
  title: string;
  sentiment: SentimentLabel | string;
}
```

To:

```typescript
export interface NewsEventMarkerItem {
  id: number;
  title: string;
  sentiment: SentimentLabel | string;
  summary: string;
}
```

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds (no code yet consumes `summary`, type is additive)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(types): add summary to NewsEventMarkerItem"
```

---

### Task 3: Create `KlineNewsTooltip.vue` — hover tooltip

**Files:**
- Create: `frontend/src/components/watchlist/KlineNewsTooltip.vue`

- [ ] **Step 1: Create the tooltip component**

Create `frontend/src/components/watchlist/KlineNewsTooltip.vue`:

```vue
<script setup lang="ts">
import type { NewsEventMarker } from '../../types/api';

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#3b82f6',
  mixed: '#a855f7',
  unknown: '#94a3b8',
};

defineProps<{
  event: NewsEventMarker;
  x: number;
  y: number;
  visible: boolean;
}>();
</script>

<template>
  <Transition name="tooltip-fade">
    <div
      v-if="visible && event.items.length"
      class="pointer-events-none fixed z-50 max-w-[280px] rounded-[12px] border border-border/70 bg-[rgba(10,17,27,0.95)] px-3 py-2 shadow-lg"
      :style="{ left: `${x}px`, top: `${y}px` }"
    >
      <div v-for="(item, i) in event.items.slice(0, 3)" :key="item.id" class="flex items-start gap-2 py-0.5" :class="i > 0 ? 'border-t border-border/30 mt-0.5' : ''">
        <span class="mt-[5px] h-[6px] w-[6px] shrink-0 rounded-full" :style="{ backgroundColor: SENTIMENT_COLORS[item.sentiment] ?? '#94a3b8' }" />
        <span class="text-[11px] leading-[1.4] text-text/90">{{ item.title.length > 40 ? item.title.slice(0, 40) + '...' : item.title }}</span>
      </div>
      <div v-if="event.items.length > 3" class="mt-1 text-[10px] text-text-faint">+{{ event.items.length - 3 }} more</div>
    </div>
  </Transition>
</template>

<style scoped>
.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.15s ease;
}
.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds (component not yet imported)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/watchlist/KlineNewsTooltip.vue
git commit -m "feat(kline): add KlineNewsTooltip hover component"
```

---

### Task 4: Create `KlineNewsPopup.vue` — click popup

**Files:**
- Create: `frontend/src/components/watchlist/KlineNewsPopup.vue`

- [ ] **Step 1: Create the popup component**

Create `frontend/src/components/watchlist/KlineNewsPopup.vue`:

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import type { NewsEventMarker } from '../../types/api';

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#3b82f6',
  mixed: '#a855f7',
  unknown: '#94a3b8',
};

const SENTIMENT_LABELS: Record<string, string> = {
  positive: '正面',
  negative: '负面',
  neutral: '中性',
  mixed: '混合',
  unknown: '未知',
};

const props = defineProps<{
  event: NewsEventMarker;
  x: number;
  y: number;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    emit('close');
  }
}

function handleBackdropClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('[data-role="kline-news-popup"]')) {
    emit('close');
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-40" @click="handleBackdropClick" />
    <Transition name="popup-fade">
      <div
        v-if="visible"
        data-role="kline-news-popup"
        class="fixed z-50 max-h-[360px] w-[320px] overflow-y-auto rounded-[14px] border border-border/70 bg-[rgba(7,12,22,0.96)] px-3.5 py-3 shadow-xl"
        :style="{ left: `${Math.min(x, window.innerWidth - 340)}px`, top: `${Math.min(y, window.innerHeight - 380)}px` }"
      >
        <header class="mb-2 flex items-center justify-between">
          <span class="text-[11px] uppercase tracking-[0.16em] text-[#ffb77d]">{{ event.time }}</span>
          <button type="button" class="text-[11px] text-text-faint hover:text-text" @click="emit('close')">×</button>
        </header>
        <div class="grid gap-2.5">
          <article v-for="item in event.items" :key="item.id" class="grid gap-1 rounded-[10px] border border-border/40 bg-[rgba(255,255,255,0.02)] px-2.5 py-2">
            <div class="flex items-start gap-2">
              <span
                class="mt-[3px] shrink-0 rounded-full px-1.5 py-[1px] text-[9px] font-medium uppercase"
                :style="{ backgroundColor: SENTIMENT_COLORS[item.sentiment] + '22', color: SENTIMENT_COLORS[item.sentiment] }"
              >
                {{ SENTIMENT_LABELS[item.sentiment] ?? item.sentiment }}
              </span>
              <span class="text-[12px] leading-[1.4] font-medium text-text">{{ item.title }}</span>
            </div>
            <p v-if="item.summary" class="line-clamp-3 text-[11px] leading-[1.4] text-text-faint">{{ item.summary }}</p>
          </article>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.popup-fade-enter-active,
.popup-fade-leave-active {
  transition: opacity 0.15s ease;
}
.popup-fade-enter-from,
.popup-fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/watchlist/KlineNewsPopup.vue
git commit -m "feat(kline): add KlineNewsPopup click detail component"
```

---

### Task 5: Integrate markers + tooltip + popup into `KlineChart.vue`

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`

This is the main integration task. We need to:
1. Import new components
2. Add state for tooltip/popup
3. Build markers from `news_events` and call `setMarkers()`
4. Subscribe to crosshair move and click events
5. Add components to template

- [ ] **Step 1: Add imports and state**

At the top of `<script setup>`, add `NewsEventMarkerItem` to the existing type import (line 13-19) and add component imports after existing ones (after line 26):

In the existing type import block, add `NewsEventMarkerItem`:
```typescript
import type {
  KlineDrawing,
  KlineDrawingStyle,
  KlineSubIndicator,
  NewsEventMarker,
  NewsEventMarkerItem,
  StockKlineResponse,
  WatchlistDashboardPeriod,
} from '../../types/api';
```

After existing component imports (after line 26):
```typescript
import KlineNewsTooltip from './KlineNewsTooltip.vue';
import KlineNewsPopup from './KlineNewsPopup.vue';
```

Add state refs after `labelEditingActive` (after line ~79):

```typescript
const newsEventsByTime = computed(() => {
  const map: Record<string, NewsEventMarker> = {};
  for (const event of props.klineData?.news_events ?? []) {
    map[event.time] = event;
  }
  return map;
});

const tooltipState = ref<{ visible: boolean; x: number; y: number; event: NewsEventMarker | null }>({
  visible: false,
  x: 0,
  y: 0,
  event: null,
});

const popupState = ref<{ visible: boolean; x: number; y: number; event: NewsEventMarker | null }>({
  visible: false,
  x: 0,
  y: 0,
  event: null,
});

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#3b82f6',
  mixed: '#a855f7',
  unknown: '#94a3b8',
};
```

- [ ] **Step 2: Add helper functions**

Add these functions after `renderChart()` (after line ~363):

```typescript
function getDominantSentiment(items: NewsEventMarkerItem[]): string {
  const counts: Record<string, number> = {};
  for (const item of items) {
    counts[item.sentiment] = (counts[item.sentiment] ?? 0) + 1;
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'unknown';
}

function buildMarkers(events: NewsEventMarker[]): Array<{ time: string; position: 'belowBar'; color: string; shape: 'circle'; text: string; size: number }> {
  return events.map((event) => {
    const dominant = getDominantSentiment(event.items);
    return {
      time: event.time,
      position: 'belowBar' as const,
      color: SENTIMENT_COLORS[dominant] ?? '#94a3b8',
      shape: 'circle' as const,
      text: `${event.items.length}`,
      size: Math.min(2 + event.items.length, 6),
    };
  });
}
```

- [ ] **Step 3: Add marker rendering to `renderChart()`**

Inside `renderChart()`, after `chart.timeScale().fitContent();` (line ~361), add:

```typescript
  // News markers
  const newsEvents = props.klineData?.news_events ?? [];
  if (newsEvents.length && candleSeries) {
    const markers = buildMarkers(newsEvents);
    markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    (candleSeries as any).setMarkers(markers);
  }
```

Note: `setMarkers` must be called on the candlestick series and markers must be sorted by time ascending.

- [ ] **Step 4: Subscribe to chart events for tooltip and popup**

Add a new function after `renderChart()` and call it from the watch on `klineData`:

```typescript
function setupChartInteractions() {
  if (!chart) return;

  // Use a flag to avoid duplicate subscriptions across re-renders
  if ((chart as any).__newsInteractionsAttached) return;
  (chart as any).__newsInteractionsAttached = true;

  chart.subscribeCrosshairMove((param: any) => {
    if (!param.time || !param.point) {
      tooltipState.value.visible = false;
      return;
    }
    const event = newsEventsByTime.value[param.time as string];
    if (!event) {
      tooltipState.value.visible = false;
      return;
    }
    const rect = mainChartRef.value?.getBoundingClientRect();
    if (!rect) return;
    tooltipState.value = {
      visible: true,
      x: rect.left + (param.point.x ?? 0) + 12,
      y: rect.top + (param.point.y ?? 0) - 10,
      event,
    };
  });

  chart.subscribeClick((param: any) => {
    tooltipState.value.visible = false;
    if (!param.time || !param.point) {
      popupState.value.visible = false;
      return;
    }
    const event = newsEventsByTime.value[param.time as string];
    if (!event) {
      popupState.value.visible = false;
      return;
    }
    const rect = mainChartRef.value?.getBoundingClientRect();
    if (!rect) return;
    popupState.value = {
      visible: true,
      x: rect.left + (param.point.x ?? 0) + 12,
      y: rect.top + (param.point.y ?? 0) + 20,
      event,
    };
  });
}
```

Then in the watch on `klineData` (line ~562), add `setupChartInteractions();` right after `renderChart();`:

```typescript
watch(
  () => [props.klineData?.symbol, props.klineData?.candles.length],
  () => {
    hoveredAnchor.value = null;
    labelEditingActive.value = false;
    chartStore.selectDrawing(null);
    chartStore.cancelDraft();
    if (props.klineData?.symbol) {
      chartStore.hydrateForSymbol(props.klineData.symbol, props.klineData.candles);
      renderChart();
      setupChartInteractions();
    }
  },
  { immediate: true },
);
```

- [ ] **Step 5: Add tooltip and popup components to template**

In the `<template>`, after the `KlineDrawingSelectionPopover` closing tag (after line ~690), add:

```html
              <KlineNewsTooltip
                :event="tooltipState.event!"
                :x="tooltipState.x"
                :y="tooltipState.y"
                :visible="tooltipState.visible"
              />
              <KlineNewsPopup
                :event="popupState.event!"
                :x="popupState.x"
                :y="popupState.y"
                :visible="popupState.visible"
                @close="popupState.visible = false"
              />
```

- [ ] **Step 6: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/watchlist/KlineChart.vue
git commit -m "feat(kline): integrate news markers with tooltip and popup on chart"
```

---

### Task 6: Update code change log

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Add entry to code change log**

Append to `docs/code-change-log.md`:

```markdown
## 2026-03-28 — K-line News Markers

### Changed
- `backend/app/schemas/market.py`: Added `summary` field to `NewsEventItemView`
- `backend/app/services/market_chart_service.py`: Extract `summary` in `_align_news_events()`
- `frontend/src/types/api.ts`: Added `summary` to `NewsEventMarkerItem`
- `frontend/src/components/watchlist/KlineChart.vue`: Added sentiment-colored markers on candlestick chart via `setMarkers()`, crosshair hover tooltip, and click popup for news details
- `frontend/src/components/watchlist/KlineNewsTooltip.vue`: New hover tooltip showing news titles + sentiment
- `frontend/src/components/watchlist/KlineNewsPopup.vue`: New click popup showing news titles + summaries
```

- [ ] **Step 2: Commit**

```bash
git add docs/code-change-log.md
git commit -m "docs: add kline news markers to code change log"
```

---

## Verification

After all tasks are complete:

1. `conda run -n news-caught pytest backend/tests -v` — all backend tests pass
2. `npm --prefix frontend run build` — frontend builds successfully
3. Visual check: open watchlist detail page, markers appear below candles on dates with news
4. Hover: tooltip shows titles with sentiment dots
5. Click: popup shows titles + summaries in compact font
6. Escape: closes popup
7. Click outside: closes popup
