import type { IChartApi } from 'lightweight-charts';
import type { ISeriesApi } from 'lightweight-charts';
import { computed, ref, type ComputedRef, type Ref } from 'vue';

import type { NewsEventMarker, NewsEventMarkerItem, StockKlineResponse } from '../types/api';

export const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#ff6f86',
  negative: '#39c884',
  neutral: '#3b82f6',
  mixed: '#a855f7',
  unknown: '#94a3b8',
};

export type ChartMarker = {
  time: string;
  position: 'belowBar';
  color: string;
  shape: 'circle';
  text: string;
  size: number;
};

export function getDominantSentiment(items: NewsEventMarkerItem[]): string {
  const counts: Record<string, number> = {};
  for (const item of items) {
    counts[item.sentiment] = (counts[item.sentiment] ?? 0) + 1;
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'unknown';
}

export function buildMarkers(events: NewsEventMarker[]): ChartMarker[] {
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

export function bindMarkersToSeries(
  candleSeries: ISeriesApi<'Candlestick'> | null,
  events: NewsEventMarker[],
) {
  const markerApi = candleSeries as {
    setMarkers?: (markers: ChartMarker[]) => void;
  } | null;
  if (!markerApi?.setMarkers) {
    return;
  }
  const markers = buildMarkers(events);
  markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  markerApi.setMarkers(markers);
}

export function useKlineMarkers(
  klineData: ComputedRef<StockKlineResponse | null>,
  mainChartRef: Ref<HTMLElement | null>,
) {
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

  const newsEventsByTime = computed(() => {
    const map: Record<string, NewsEventMarker> = {};
    for (const event of klineData.value?.news_events ?? []) {
      map[event.time] = event;
    }
    return map;
  });

  function setupChartInteractions(chart: IChartApi | null) {
    if (!chart) {
      return;
    }

    if ((chart as { __newsInteractionsAttached?: boolean }).__newsInteractionsAttached) {
      return;
    }
    (chart as { __newsInteractionsAttached?: boolean }).__newsInteractionsAttached = true;

    chart.subscribeCrosshairMove((param) => {
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
      if (!rect) {
        return;
      }
      tooltipState.value = {
        visible: true,
        x: rect.left + (param.point.x ?? 0) + 12,
        y: rect.top + (param.point.y ?? 0) - 10,
        event,
      };
    });

    chart.subscribeClick((param) => {
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
      if (!rect) {
        return;
      }
      popupState.value = {
        visible: true,
        x: rect.left + (param.point.x ?? 0) + 12,
        y: rect.top + (param.point.y ?? 0) + 20,
        event,
      };
    });
  }

  return {
    tooltipState,
    popupState,
    newsEventsByTime,
    setupChartInteractions,
    bindMarkersToSeries: (candleSeries: ISeriesApi<'Candlestick'> | null) =>
      bindMarkersToSeries(candleSeries, klineData.value?.news_events ?? []),
  };
}
