<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import { useKlineDrawingInteraction } from '../../composables/useKlineDrawingInteraction';
import type { KlineCandle, KlineDrawing, KlineDrawingAnchor, KlineDrawingTool } from '../../types/api';
import { isEditableDrawing, resolveLabelEditorText } from '../../utils/klineDrawings';
import {
  buildCrosshairProjection,
  computeAnchorFromPoint,
  computeFibonacciLevels,
  hitTestDrawing,
  projectAnchorToPoint,
  resolveEventClientPoint,
  toLocalPoint,
  touchPointsFromEvent,
  type KlineChartProjector,
  type ProjectedPoint,
} from '../../utils/klineOverlayGeometry';

const props = defineProps<{
  symbol: string | null;
  candles: KlineCandle[];
  drawings: KlineDrawing[];
  draftAnchors?: KlineDrawingAnchor[] | null;
  activeTool: KlineDrawingTool;
  selectedDrawingId: string | null;
  disabled?: boolean;
  chartProjector?: KlineChartProjector | null;
}>();

const emit = defineEmits<{
  draftStart: [anchor: KlineDrawingAnchor];
  draftUpdate: [anchor: KlineDrawingAnchor];
  draftCommit: [];
  draftCancel: [];
  drawingSelect: [selection: { id: string | null; append: boolean }];
  labelEditingChange: [editing: boolean];
  hoverAnchorChange: [anchor: KlineDrawingAnchor | null];
  drawingAnchorCommit: [drawingId: string, anchors: KlineDrawingAnchor[]];
  drawingMoveCommit: [drawingId: string, anchors: KlineDrawingAnchor[]];
  drawingLabelCommit: [drawingId: string, text: string];
}>();

const overlayRef = ref<HTMLElement | null>(null);
const overlayDisabled = computed(() => props.disabled || !props.candles.length || !props.symbol);
const overlaySize = ref({ width: 0, height: 0 });
const hoverAnchor = ref<KlineDrawingAnchor | null>(null);
const editingLabel = ref<{ drawingId: string; text: string } | null>(null);
const editorInputRef = ref<HTMLInputElement | null>(null);
const pointerPassthroughActive = ref(false);
const touchPassthroughTarget = ref<EventTarget | null>(null);
const { dragState, beginAnchorDrag: startAnchorDrag, beginBodyDrag: startBodyDrag, endDrag, resolveDragCommit } = useKlineDrawingInteraction();
let resizeObserver: ResizeObserver | null = null;

function getOverlayRect() {
  return overlayRef.value?.getBoundingClientRect() ?? null;
}

function refreshSize() {
  if (!overlayRef.value) {
    return;
  }
  overlaySize.value = {
    width: overlayRef.value.clientWidth,
    height: overlayRef.value.clientHeight,
  };
}

function buildAnchor(event: MouseEvent | TouchEvent): KlineDrawingAnchor | null {
  const rect = getOverlayRect();
  if (!rect) {
    return null;
  }
  const point = resolveEventClientPoint(event);
  if (!point) {
    return null;
  }
  return computeAnchorFromPoint(point, rect, props.candles, props.chartProjector);
}

function projectAnchor(anchor: KlineDrawingAnchor, target: HTMLElement): ProjectedPoint | null {
  return projectAnchorToPoint(anchor, props.candles, target.getBoundingClientRect());
}

function drawingPoints(drawing: KlineDrawing) {
  if (!overlayRef.value) {
    return [];
  }
  return drawing.anchors
    .map((anchor) => projectAnchor(anchor, overlayRef.value!))
    .filter((item): item is ProjectedPoint => item !== null);
}

function pointFromEvent(event: MouseEvent | WheelEvent | TouchEvent, target: HTMLElement) {
  const point = resolveEventClientPoint(event);
  if (!point) {
    return null;
  }
  return toLocalPoint(point, target.getBoundingClientRect());
}

function hitDrawingAtEvent(event: MouseEvent | WheelEvent | TouchEvent) {
  const target = overlayRef.value;
  if (!target) {
    return null;
  }
  const point = pointFromEvent(event, target);
  if (!point) {
    return null;
  }
  return [...props.drawings]
    .reverse()
    .find((drawing) => drawing.visible && hitTestDrawing(drawing, point, (drawingAnchor) => projectAnchor(drawingAnchor, target))) ?? null;
}

function selectedDrawing() {
  return props.drawings.find((drawing) => drawing.id === props.selectedDrawingId) ?? null;
}

const crosshair = computed(() =>
  buildCrosshairProjection({
    anchor: hoverAnchor.value,
    candles: props.candles,
    width: overlaySize.value.width,
    height: overlaySize.value.height,
    projector: props.chartProjector,
  }),
);

const overlayTouchAction = computed(() => (overlayDisabled.value ? 'auto' : 'none'));

function fibLevels(points: ProjectedPoint[]) {
  return computeFibonacciLevels(points);
}

function onClick(event: MouseEvent) {
  if (overlayDisabled.value) {
    emit('drawingSelect', { id: null, append: false });
    return;
  }
  const anchor = buildAnchor(event);
  if (!anchor) {
    return;
  }
  const hit = hitDrawingAtEvent(event);
  if (props.activeTool === 'select') {
    emit('drawingSelect', { id: hit?.id ?? null, append: Boolean(event.shiftKey) });
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
  if (overlayDisabled.value) {
    hoverAnchor.value = null;
    emit('hoverAnchorChange', null);
    return;
  }
  const anchor = buildAnchor(event);
  hoverAnchor.value = anchor;
  emit('hoverAnchorChange', anchor);
  if (anchor && props.activeTool !== 'select' && !dragState.value) {
    emit('draftUpdate', anchor);
  }
}

function forwardMouseDownToChart(event: MouseEvent) {
  if (!overlayRef.value) {
    return;
  }
  pointerPassthroughActive.value = true;
  overlayRef.value.style.pointerEvents = 'none';
  const target = document.elementFromPoint(event.clientX, event.clientY);
  if (!target) {
    pointerPassthroughActive.value = false;
    overlayRef.value.style.pointerEvents = '';
    return;
  }
  target.dispatchEvent(
    new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      button: event.button,
      buttons: event.buttons,
      ctrlKey: event.ctrlKey,
      shiftKey: event.shiftKey,
      altKey: event.altKey,
      metaKey: event.metaKey,
    }),
  );
}

function forwardWheelToChart(event: WheelEvent) {
  if (!overlayRef.value) {
    return;
  }
  overlayRef.value.style.pointerEvents = 'none';
  const target = document.elementFromPoint(event.clientX, event.clientY);
  overlayRef.value.style.pointerEvents = pointerPassthroughActive.value ? 'none' : '';
  if (!target) {
    return;
  }
  target.dispatchEvent(
    new WheelEvent('wheel', {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      deltaX: event.deltaX,
      deltaY: event.deltaY,
      deltaZ: event.deltaZ,
      ctrlKey: event.ctrlKey,
      shiftKey: event.shiftKey,
      altKey: event.altKey,
      metaKey: event.metaKey,
    }),
  );
}

function createForwardedTouchEvent(type: 'touchstart' | 'touchmove' | 'touchend' | 'touchcancel', source: TouchEvent) {
  const touchPoints = touchPointsFromEvent(source);
  const activeTouches = type === 'touchend' || type === 'touchcancel' ? [] : touchPoints;
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    touches: {
      value: activeTouches,
      configurable: true,
    },
    changedTouches: {
      value: touchPoints,
      configurable: true,
    },
    __klineForwardedTouch: {
      value: true,
      configurable: true,
    },
  });
  return event;
}

function cleanupTouchPassthrough() {
  touchPassthroughTarget.value = null;
}

function forwardTouchEventToChart(type: 'touchstart' | 'touchmove' | 'touchend' | 'touchcancel', event: TouchEvent) {
  if (!overlayRef.value) {
    return;
  }
  if (type === 'touchstart') {
    overlayRef.value.style.pointerEvents = 'none';
    const point = resolveEventClientPoint(event);
    const target = point ? document.elementFromPoint(point.clientX, point.clientY) : null;
    overlayRef.value.style.pointerEvents = '';
    if (!target) {
      cleanupTouchPassthrough();
      return;
    }
    touchPassthroughTarget.value = target;
  }
  const target = touchPassthroughTarget.value;
  if (!target || !(target instanceof EventTarget)) {
    cleanupTouchPassthrough();
    return;
  }
  target.dispatchEvent(createForwardedTouchEvent(type, event));
  if (type === 'touchend' || type === 'touchcancel') {
    cleanupTouchPassthrough();
  }
}

function onMousedown(event: MouseEvent) {
  if (
    overlayDisabled.value ||
    props.activeTool !== 'select' ||
    dragState.value ||
    editingLabel.value ||
    hitDrawingAtEvent(event)
  ) {
    return;
  }
  forwardMouseDownToChart(event);
}

function onWheel(event: WheelEvent) {
  if (overlayDisabled.value || props.activeTool !== 'select' || dragState.value || editingLabel.value || hitDrawingAtEvent(event)) {
    return;
  }
  event.preventDefault();
  forwardWheelToChart(event);
}

function onTouchstart(event: TouchEvent) {
  if (
    overlayDisabled.value ||
    props.activeTool !== 'select' ||
    dragState.value ||
    editingLabel.value ||
    hitDrawingAtEvent(event)
  ) {
    return;
  }
  event.preventDefault();
  forwardTouchEventToChart('touchstart', event);
}

function onTouchmove(event: TouchEvent) {
  if ((event as TouchEvent & { __klineForwardedTouch?: boolean }).__klineForwardedTouch || !touchPassthroughTarget.value) {
    return;
  }
  event.preventDefault();
  forwardTouchEventToChart('touchmove', event);
}

function onTouchend(event: TouchEvent) {
  if ((event as TouchEvent & { __klineForwardedTouch?: boolean }).__klineForwardedTouch || !touchPassthroughTarget.value) {
    return;
  }
  event.preventDefault();
  forwardTouchEventToChart('touchend', event);
}

function onTouchcancel(event: TouchEvent) {
  if ((event as TouchEvent & { __klineForwardedTouch?: boolean }).__klineForwardedTouch || !touchPassthroughTarget.value) {
    return;
  }
  event.preventDefault();
  forwardTouchEventToChart('touchcancel', event);
}

function onKeydown(event: KeyboardEvent) {
  if (editingLabel.value) {
    if (event.key === 'Escape') {
      cancelLabelEdit();
      event.stopPropagation();
    }
    return;
  }
  if (event.key === 'Escape') {
    if (hasDraft.value) {
      emit('draftCancel');
      event.stopPropagation();
    }
    return;
  }
  if (event.key === 'Enter') {
    const drawing = selectedDrawing();
    if (drawing?.toolType === 'price_note') {
      openLabelEditor(drawing);
      event.stopPropagation();
    }
  }
}

const hasDraft = computed(() => (props.draftAnchors?.length ?? 0) > 0);

function onMouseleave() {
  hoverAnchor.value = null;
  endDrag();
  emit('hoverAnchorChange', null);
}

function onMouseup(event: MouseEvent) {
  if (!dragState.value || overlayDisabled.value) {
    endDrag();
    return;
  }
  const drawing = props.drawings.find((item) => item.id === dragState.value?.drawingId) ?? null;
  const anchor = buildAnchor(event);
  const commit = resolveDragCommit(drawing, anchor, props.candles);
  if (commit?.type === 'anchor') {
    emit('drawingAnchorCommit', commit.drawingId, commit.anchors);
  } else if (commit?.type === 'move') {
    emit('drawingMoveCommit', commit.drawingId, commit.anchors);
  }
  endDrag();
}

function beginAnchorDrag(drawingId: string, anchorIndex: number, event: MouseEvent) {
  const drawing = props.drawings.find((item) => item.id === drawingId) ?? null;
  const anchor = buildAnchor(event);
  startAnchorDrag(drawing, anchorIndex, anchor);
}

function beginBodyDrag(drawingId: string, event: MouseEvent) {
  const drawing = props.drawings.find((item) => item.id === drawingId) ?? null;
  const anchor = buildAnchor(event);
  startBodyDrag(drawing, anchor);
}

function handleWindowMouseup() {
  endDrag();
  if (overlayRef.value) {
    overlayRef.value.style.pointerEvents = '';
  }
}

function openLabelEditor(drawing: KlineDrawing) {
  if (drawing.toolType !== 'price_note') {
    return;
  }
  editingLabel.value = {
    drawingId: drawing.id,
    text: resolveLabelEditorText(drawing),
  };
  emit('labelEditingChange', true);
  nextTick(() => editorInputRef.value?.focus());
}

function commitLabelEdit() {
  if (!editingLabel.value) {
    return;
  }
  emit('drawingLabelCommit', editingLabel.value.drawingId, editingLabel.value.text);
  editingLabel.value = null;
  emit('labelEditingChange', false);
}

function cancelLabelEdit() {
  if (!editingLabel.value) {
    return;
  }
  editingLabel.value = null;
  emit('labelEditingChange', false);
}

function handleLabelInputBlur() {
  cancelLabelEdit();
}

onMounted(() => {
  refreshSize();
  window.addEventListener('resize', refreshSize);
  window.addEventListener('mouseup', handleWindowMouseup);
  if (typeof ResizeObserver !== 'undefined' && overlayRef.value) {
    resizeObserver = new ResizeObserver(() => refreshSize());
    resizeObserver.observe(overlayRef.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', refreshSize);
  window.removeEventListener('mouseup', handleWindowMouseup);
  cleanupTouchPassthrough();
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <div
    ref="overlayRef"
    class="absolute inset-0 z-10"
    data-role="kline-drawing-overlay"
    tabindex="0"
    :style="{ touchAction: overlayTouchAction }"
    @click="onClick"
    @mousedown="onMousedown"
    @mousemove="onMousemove"
    @mouseleave="onMouseleave"
    @mouseup="onMouseup"
    @wheel="onWheel"
    @touchstart="onTouchstart"
    @touchmove="onTouchmove"
    @touchend="onTouchend"
    @touchcancel="onTouchcancel"
    @keydown="onKeydown"
  >
    <svg class="h-full w-full">
      <g v-for="drawing in drawings.filter((item) => item.visible)" :key="drawing.id" :data-role="`drawing-${drawing.id}`">
        <line
          v-if="drawing.toolType === 'trend_line' && drawingPoints(drawing).length >= 2"
          :data-role="`drawing-body-${drawing.id}`"
          :x1="drawingPoints(drawing)[0]?.x"
          :y1="drawingPoints(drawing)[0]?.y"
          :x2="drawingPoints(drawing)[1]?.x"
          :y2="drawingPoints(drawing)[1]?.y"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :stroke-dasharray="drawing.style.lineStyle === 'dashed' ? '6 4' : undefined"
          :opacity="selectedDrawingId === drawing.id ? 1 : 0.78"
          @mousedown.stop="beginBodyDrag(drawing.id, $event)"
          @touchstart.stop
        />
        <line
          v-else-if="(drawing.toolType === 'horizontal_line' || drawing.toolType === 'price_note') && drawingPoints(drawing).length >= 1"
          :data-role="`drawing-body-${drawing.id}`"
          x1="0"
          :y1="drawingPoints(drawing)[0]?.y"
          :x2="overlaySize.width"
          :y2="drawingPoints(drawing)[0]?.y"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :stroke-dasharray="drawing.style.lineStyle === 'dashed' ? '6 4' : undefined"
          @mousedown.stop="beginBodyDrag(drawing.id, $event)"
          @touchstart.stop
        />
        <rect
          v-else-if="drawing.toolType === 'price_range' && drawingPoints(drawing).length >= 2"
          :data-role="`drawing-body-${drawing.id}`"
          :x="Math.min(drawingPoints(drawing)[0]?.x ?? 0, drawingPoints(drawing)[1]?.x ?? 0)"
          :y="Math.min(drawingPoints(drawing)[0]?.y ?? 0, drawingPoints(drawing)[1]?.y ?? 0)"
          :width="Math.abs((drawingPoints(drawing)[0]?.x ?? 0) - (drawingPoints(drawing)[1]?.x ?? 0))"
          :height="Math.abs((drawingPoints(drawing)[0]?.y ?? 0) - (drawingPoints(drawing)[1]?.y ?? 0))"
          :stroke="drawing.style.color"
          :stroke-width="drawing.style.lineWidth"
          :fill="drawing.style.color"
          :fill-opacity="drawing.style.fillOpacity"
          @mousedown.stop="beginBodyDrag(drawing.id, $event)"
          @touchstart.stop
        />
        <g
          v-else-if="drawing.toolType === 'fibonacci_retracement' && drawingPoints(drawing).length >= 2"
          :data-role="`drawing-body-${drawing.id}`"
          @mousedown.stop="beginBodyDrag(drawing.id, $event)"
          @touchstart.stop
        >
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
        <text
          v-if="drawing.toolType === 'price_note' && drawingPoints(drawing).length >= 1"
          :data-role="`price-note-label-${drawing.id}`"
          :x="Math.min((drawingPoints(drawing)[0]?.x ?? 0) + 8, Math.max(overlaySize.width - 80, 8))"
          :y="(drawingPoints(drawing)[0]?.y ?? 0) - 8"
          fill="#f8fafc"
          font-size="12"
          @dblclick.stop="openLabelEditor(drawing)"
          @touchstart.stop
        >
          {{ drawing.payload.text }}
        </text>
        <circle
          v-for="(point, index) in selectedDrawingId === drawing.id && isEditableDrawing(drawing) ? drawingPoints(drawing) : []"
          :key="`${drawing.id}-${index}`"
          :data-role="`drawing-anchor-handle-${drawing.id}-${index}`"
          :cx="point.x"
          :cy="point.y"
          r="5"
          fill="#f8fafc"
          stroke="#0f172a"
          stroke-width="1.5"
          @mousedown.stop="beginAnchorDrag(drawing.id, index, $event)"
          @touchstart.stop
        />
      </g>
      <g v-if="crosshair">
        <line data-role="crosshair-vertical" :x1="crosshair.x" y1="0" :x2="crosshair.x" :y2="overlaySize.height" stroke="rgba(58,210,230,0.45)" stroke-dasharray="5 4" />
        <line data-role="crosshair-horizontal" x1="0" :y1="crosshair.y" :x2="overlaySize.width" :y2="crosshair.y" stroke="rgba(58,210,230,0.35)" stroke-dasharray="5 4" />
        <text data-role="crosshair-time-label" :x="Math.max(8, crosshair.x - 34)" :y="overlaySize.height - 8" fill="#f8fafc" font-size="11">
          {{ crosshair.timeLabel }}
        </text>
        <text data-role="crosshair-price-label" :x="Math.max(8, overlaySize.width - 56)" :y="Math.max(14, crosshair.y - 6)" fill="#3ad2e6" font-size="11">
          {{ crosshair.priceLabel }}
        </text>
      </g>
      <g v-if="hasDraft" data-role="drawing-draft-preview">
        <line x1="20" y1="20" x2="120" y2="120" stroke="#3ad2e6" stroke-width="2" stroke-dasharray="6 4" />
      </g>
    </svg>
    <div
      v-if="editingLabel"
      class="absolute inset-x-3 top-3 z-20 flex justify-end"
    >
      <input
        ref="editorInputRef"
        data-role="price-note-editor-input"
        v-model="editingLabel.text"
        class="w-40 rounded-md border border-border bg-[rgba(7,12,22,0.96)] px-2 py-1 text-xs text-text outline-none"
        autofocus
        maxlength="24"
        @keydown.enter.stop.prevent="commitLabelEdit"
        @keydown.esc.stop.prevent="cancelLabelEdit"
        @blur="handleLabelInputBlur"
      />
    </div>
  </div>
</template>
