<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import type { KlineCandle, KlineDrawing, KlineDrawingAnchor, KlineDrawingTool } from '../../types/api';
import { hitTestDrawing, remapAnchorTime, type ProjectedPoint } from '../../utils/klineOverlayGeometry';

const props = defineProps<{
  symbol: string | null;
  candles: KlineCandle[];
  drawings: KlineDrawing[];
  draftAnchors?: KlineDrawingAnchor[] | null;
  activeTool: KlineDrawingTool;
  selectedDrawingId: string | null;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  draftStart: [anchor: KlineDrawingAnchor];
  draftUpdate: [anchor: KlineDrawingAnchor];
  draftCommit: [];
  draftCancel: [];
  drawingSelect: [id: string | null];
}>();

const overlayRef = ref<HTMLElement | null>(null);
const overlayDisabled = computed(() => props.disabled || !props.candles.length || !props.symbol);
const overlaySize = ref({ width: 0, height: 0 });

function refreshSize() {
  if (!overlayRef.value) {
    return;
  }
  overlaySize.value = {
    width: overlayRef.value.clientWidth,
    height: overlayRef.value.clientHeight,
  };
}

function buildAnchor(event: MouseEvent): KlineDrawingAnchor | null {
  if (!props.candles.length) {
    return null;
  }
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const index = Math.max(0, Math.min(props.candles.length - 1, Math.round(((event.clientX - rect.left) / Math.max(rect.width, 1)) * (props.candles.length - 1))));
  const candle = props.candles[index];
  const high = Math.max(...props.candles.map((item) => item.high));
  const low = Math.min(...props.candles.map((item) => item.low));
  const ratio = 1 - (event.clientY - rect.top) / Math.max(rect.height, 1);
  return {
    time: candle.time,
    price: low + (high - low) * ratio,
  };
}

function projectAnchor(anchor: KlineDrawingAnchor, target: HTMLElement): ProjectedPoint | null {
  if (!props.candles.length) {
    return null;
  }
  const rect = target.getBoundingClientRect();
  const mappedTime = remapAnchorTime(anchor, props.candles);
  const index = Math.max(
    0,
    props.candles.findIndex((candle) => candle.time === mappedTime),
  );
  const high = Math.max(...props.candles.map((item) => item.high));
  const low = Math.min(...props.candles.map((item) => item.low));
  const x = props.candles.length > 1 ? (index / (props.candles.length - 1)) * rect.width : rect.width / 2;
  const y = high === low ? rect.height / 2 : (1 - (anchor.price - low) / (high - low)) * rect.height;
  return { x, y };
}

function drawingPoints(drawing: KlineDrawing) {
  return drawing.anchors
    .map((anchor) => projectAnchor(anchor, overlayRef.value!))
    .filter((item): item is ProjectedPoint => item !== null);
}

function fibLevels(points: ProjectedPoint[]) {
  const [start, end] = points;
  if (!start || !end) {
    return [];
  }
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  return levels.map((level) => ({
    key: String(level),
    y: top + (bottom - top) * level,
    label: String(level),
  }));
}

function onClick(event: MouseEvent) {
  if (overlayDisabled.value) {
    emit('drawingSelect', null);
    return;
  }
  const anchor = buildAnchor(event);
  if (!anchor) {
    return;
  }
  const target = event.currentTarget as HTMLElement;
  const point = {
    x: event.clientX - target.getBoundingClientRect().left,
    y: event.clientY - target.getBoundingClientRect().top,
  };
  const hit = [...props.drawings].reverse().find(
    (drawing) => drawing.visible && hitTestDrawing(drawing, point, (drawingAnchor) => projectAnchor(drawingAnchor, target)),
  );
  if (props.activeTool === 'select') {
    emit('drawingSelect', hit?.id ?? null);
    return;
  }
  emit('draftStart', anchor);
  if (props.activeTool === 'horizontal_line' || props.activeTool === 'price_note') {
    emit('draftCommit');
  } else if ((props.draftAnchors?.length ?? 0) >= 1) {
    emit('draftCommit');
  }
}

function onMousemove(event: MouseEvent) {
  if (overlayDisabled.value || props.activeTool === 'select') {
    return;
  }
  const anchor = buildAnchor(event);
  if (anchor) {
    emit('draftUpdate', anchor);
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('draftCancel');
  }
}

const hasDraft = computed(() => (props.draftAnchors?.length ?? 0) > 0);

onMounted(() => {
  refreshSize();
  window.addEventListener('resize', refreshSize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', refreshSize);
});
</script>

<template>
  <div
    ref="overlayRef"
    class="absolute inset-0 z-10"
    data-role="kline-drawing-overlay"
    tabindex="0"
    @click="onClick"
    @mousemove="onMousemove"
    @keydown="onKeydown"
  >
    <svg class="h-full w-full">
      <g v-for="drawing in drawings.filter((item) => item.visible)" :key="drawing.id" :data-role="`drawing-${drawing.id}`">
        <line
          v-if="drawing.toolType === 'trend_line' && drawingPoints(drawing).length >= 2"
          :x1="drawingPoints(drawing)[0]?.x"
          :y1="drawingPoints(drawing)[0]?.y"
          :x2="drawingPoints(drawing)[1]?.x"
          :y2="drawingPoints(drawing)[1]?.y"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :stroke-dasharray="drawing.style.lineStyle === 'dashed' ? '6 4' : undefined"
          :opacity="selectedDrawingId === drawing.id ? 1 : 0.78"
        />
        <line
          v-else-if="(drawing.toolType === 'horizontal_line' || drawing.toolType === 'price_note') && drawingPoints(drawing).length >= 1"
          x1="0"
          :y1="drawingPoints(drawing)[0]?.y"
          :x2="overlaySize.width"
          :y2="drawingPoints(drawing)[0]?.y"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :stroke-dasharray="drawing.style.lineStyle === 'dashed' ? '6 4' : undefined"
        />
        <rect
          v-else-if="drawing.toolType === 'price_range' && drawingPoints(drawing).length >= 2"
          :x="Math.min(drawingPoints(drawing)[0]?.x ?? 0, drawingPoints(drawing)[1]?.x ?? 0)"
          :y="Math.min(drawingPoints(drawing)[0]?.y ?? 0, drawingPoints(drawing)[1]?.y ?? 0)"
          :width="Math.abs((drawingPoints(drawing)[0]?.x ?? 0) - (drawingPoints(drawing)[1]?.x ?? 0))"
          :height="Math.abs((drawingPoints(drawing)[0]?.y ?? 0) - (drawingPoints(drawing)[1]?.y ?? 0))"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :fill="drawing.style.color"
          :fill-opacity="drawing.style.fillOpacity"
        />
        <g v-else-if="drawing.toolType === 'fibonacci_retracement' && drawingPoints(drawing).length >= 2">
          <line
            v-for="level in fibLevels(drawingPoints(drawing))"
            :key="level.key"
            :x1="Math.min(drawingPoints(drawing)[0]?.x ?? 0, drawingPoints(drawing)[1]?.x ?? 0)"
            :y1="level.y"
            :x2="Math.max(drawingPoints(drawing)[0]?.x ?? 0, drawingPoints(drawing)[1]?.x ?? 0)"
            :y2="level.y"
            :stroke="drawing.style.color"
            stroke-width="1"
          />
          <text
            v-for="level in fibLevels(drawingPoints(drawing))"
            :key="`${level.key}-text`"
            :x="Math.max(drawingPoints(drawing)[0]?.x ?? 0, drawingPoints(drawing)[1]?.x ?? 0) + 6"
            :y="level.y + 4"
            fill="#f8fafc"
            font-size="11"
          >
            {{ level.label }}
          </text>
        </g>
        <text v-if="drawing.toolType === 'price_note' && drawingPoints(drawing).length >= 1" :x="Math.min((drawingPoints(drawing)[0]?.x ?? 0) + 8, Math.max(overlaySize.width - 80, 8))" :y="(drawingPoints(drawing)[0]?.y ?? 0) - 8" fill="#f8fafc" font-size="12">
          {{ drawing.payload.text }}
        </text>
      </g>
      <g v-if="hasDraft" data-role="drawing-draft-preview">
        <line x1="20" y1="20" x2="120" y2="120" stroke="#ffb66d" stroke-width="2" stroke-dasharray="6 4" />
      </g>
    </svg>
  </div>
</template>
