# K-line News Markers Design

## Goal

Show news events as clickable markers on the K-line candlestick chart. Hovering a marker shows a lightweight tooltip (title + sentiment). Clicking a marker opens a popup displaying all news titles and summaries for that trading day.

## Reference

Inspired by PokieTicker's canvas particle approach, adapted to lightweight-charts' native `setMarkers()` API for simplicity and reliability.

## Scope

### In Scope

- Backend: add `summary` field to `NewsEventItemView`
- Frontend: render markers on candlestick chart via `setMarkers()`
- Frontend: hover tooltip near marker
- Frontend: click popup with news titles + summaries
- Sentiment-based color coding for markers

### Out of Scope

- T+1 return impact visualization (future consideration)
- Category-based filtering (future consideration)
- Canvas overlay custom rendering (using native markers instead)
- News fetching independent of K-line data (using backend aggregation)

## Architecture

### Data Flow

```
Kline API (/api/market/symbols/{symbol}/kline)
  → MarketChartService._build_kline_payload()
    → NewsMentionsRepository.list_related_news(symbol)
    → _align_news_events() → [{time, items: [{id, title, sentiment, summary}]}]
  → Frontend receives klineData.news_events
  → renderChart() calls candleSeries.setMarkers()
  → User hover → tooltip
  → User click → popup
```

### Backend Changes

#### 1. `backend/app/schemas/market.py`

Add `summary` to `NewsEventItemView`:

```python
class NewsEventItemView(BaseModel):
    id: int
    title: str
    sentiment: str
    summary: str = ""
```

#### 2. `backend/app/services/market_chart_service.py`

In `_align_news_events()`, extract `summary` from news items alongside `title` and `sentiment`:

```python
"summary": str(getattr(item, "summary", "") if not isinstance(item, dict) else item.get("summary", "")),
```

This is the only backend change needed. The `NewsItem` model already has a `summary` field.

### Frontend Changes

#### 3. `frontend/src/types/api.ts`

Update `NewsEventItem` type to include `summary`:

```typescript
export interface NewsEventItem {
  id: number;
  title: string;
  sentiment: string;
  summary: string;
}
```

#### 4. `KlineChart.vue` — Marker Rendering

In `renderChart()`, after setting candle data, call `candleSeries.setMarkers()`:

```typescript
function buildMarkers(events: NewsEventGroup[]): SeriesMarker[] {
  return events.map(event => {
    const dominantSentiment = getDominantSentiment(event.items);
    return {
      time: event.time,
      position: 'belowBar',
      color: SENTIMENT_COLORS[dominantSentiment],
      shape: 'circle',
      text: `${event.items.length}`,
      size: Math.min(2 + event.items.length, 6),
    };
  });
}
```

Sentiment colors (matching existing dark theme):
- positive → `#22c55e` (green, matches down-candle color)
- negative → `#ef4444` (red)
- neutral → `#3b82f6` (blue)
- unknown → `#94a3b8` (slate)

#### 5. `KlineChart.vue` — Hover Tooltip

Subscribe to chart crosshair move events. When the crosshair is on a time that has news events, show a positioned tooltip near the marker:

```typescript
chart.subscribeCrosshairMove((param) => {
  if (!param.time) { hideTooltip(); return; }
  const event = newsEventsByTime[param.time];
  if (!event) { hideTooltip(); return; }
  showTooltip(param.point, event);
});
```

Tooltip content:
- Font size: 11px
- News title (truncated to ~40 chars)
- Sentiment badge (colored dot + label)
- Up to 3 items shown, "+N more" if more exist

Tooltip positioning: absolute, anchored near the crosshair point, with boundary clamping.

#### 6. `KlineChart.vue` — Click Popup

Subscribe to chart click events. When clicking on a marker/time with news, show a popup:

```typescript
chart.subscribeClick((param) => {
  if (!param.time) { closePopup(); return; }
  const event = newsEventsByTime[param.time];
  if (!event) { closePopup(); return; }
  openPopup(param.point, event);
});
```

Popup content:
- Date header (e.g., "2026-03-28")
- For each news item:
  - Title (bold, 12px)
  - Summary (regular, 11px, max 3 lines with ellipsis)
  - Sentiment badge (small colored chip)
- Font sizes: title 12px, summary 11px — controlled and compact

Popup positioning: centered below the chart area or to the side of the clicked point, depending on available space.

#### 7. New Component: `KlineNewsTooltip.vue`

Lightweight tooltip shown on hover:

```html
<div class="kline-news-tooltip">
  <div v-for="item in items.slice(0, 3)" class="tooltip-item">
    <span class="sentiment-dot" :style="{ background: colorFor(item.sentiment) }" />
    <span class="title">{{ item.title }}</span>
  </div>
  <div v-if="items.length > 3" class="more-hint">+{{ items.length - 3 }} more</div>
</div>
```

Styling: `text-[11px]`, `bg-[rgba(10,17,27,0.95)]`, `border border-border/70`, `rounded-[12px]`, `px-3 py-2`, max-width 280px.

#### 8. New Component: `KlineNewsPopup.vue`

Detailed popup shown on click:

```html
<div class="kline-news-popup">
  <header>
    <span class="date">{{ date }}</span>
    <button @click="close">×</button>
  </header>
  <div v-for="item in items" class="news-entry">
    <div class="flex items-center gap-2">
      <span class="sentiment-badge" :class="item.sentiment">{{ item.sentiment }}</span>
      <span class="title text-[12px]">{{ item.title }}</span>
    </div>
    <p class="summary text-[11px]">{{ item.summary }}</p>
  </div>
</div>
```

Styling: same dark theme, `text-[12px]` for titles, `text-[11px]` for summaries, `bg-[rgba(7,12,22,0.96)]`, `rounded-[14px]`, max-height with scroll if many items.

## Interaction Details

### Hover Flow

1. User moves mouse across chart
2. Crosshair moves with mouse
3. When crosshair lands on a time with news events → tooltip appears
4. When crosshair moves away → tooltip disappears
5. Tooltip does NOT block chart interaction (pointer-events: none on tooltip, or auto-hide on next move)

### Click Flow

1. User clicks on a marker or on a candle with news
2. Popup appears with full news details for that date
3. Clicking outside popup, pressing Escape, or clicking another marker closes the popup
4. Popup does NOT replace the existing news chips below the chart

### Marker Visibility

- Markers are always visible when news_events exist
- Marker size scales slightly with news count (2-6 range)
- Marker text shows count (e.g., "3" for 3 news items)
- Existing chips below chart remain as-is

## Files Changed

| File | Change |
|------|--------|
| `backend/app/schemas/market.py` | Add `summary` field to `NewsEventItemView` |
| `backend/app/services/market_chart_service.py` | Extract `summary` in `_align_news_events()` |
| `frontend/src/types/api.ts` | Add `summary` to `NewsEventItem` type |
| `frontend/src/components/watchlist/KlineChart.vue` | Add markers, tooltip, popup integration |
| `frontend/src/components/watchlist/KlineNewsTooltip.vue` | New: hover tooltip component |
| `frontend/src/components/watchlist/KlineNewsPopup.vue` | New: click popup component |

## Testing

- Backend: verify `GET /api/market/symbols/{symbol}/kline` returns `summary` in news_events items
- Frontend build: `npm --prefix frontend run build` passes
- Visual: markers render on correct dates below candles
- Interaction: hover shows tooltip, click shows popup, Escape closes popup
- Edge cases: no news (no markers), single news, many news on one day
