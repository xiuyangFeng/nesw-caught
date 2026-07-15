import { ref } from 'vue';

import type { KlineCandle, KlineDrawing, KlineDrawingAnchor } from '../types/api';
import { isDrawingDraggable, isEditableDrawing } from '../utils/klineDrawings';
import { computeCandleIndexDelta, moveDrawingByAnchor, moveDrawingByDelta } from '../utils/klineOverlayGeometry';

export type KlineDrawingDragState =
  | {
      mode: 'anchor' | 'object';
      drawingId: string;
      anchorIndex?: number;
      startAnchor: KlineDrawingAnchor;
    }
  | null;

export type KlineDrawingDragCommit =
  | { type: 'anchor'; drawingId: string; anchors: KlineDrawingAnchor[] }
  | { type: 'move'; drawingId: string; anchors: KlineDrawingAnchor[] };

/**
 * 封装 K 线画图 overlay 的拖拽状态机:锚点/整体拖拽的开始、提交与结束。
 * 仅处理与 DOM 无关的状态与判定逻辑,事件坐标 -> 锚点的换算仍由调用方
 * (KlineDrawingOverlay.vue) 完成后再传入,保持该 composable 纯粹可测。
 */
export function useKlineDrawingInteraction() {
  const dragState = ref<KlineDrawingDragState>(null);

  function beginAnchorDrag(drawing: KlineDrawing | null, anchorIndex: number, anchor: KlineDrawingAnchor | null) {
    if (!drawing || !anchor || !isDrawingDraggable(drawing)) {
      return;
    }
    dragState.value = { mode: 'anchor', drawingId: drawing.id, anchorIndex, startAnchor: anchor };
  }

  function beginBodyDrag(drawing: KlineDrawing | null, anchor: KlineDrawingAnchor | null) {
    if (!drawing || !anchor || !isDrawingDraggable(drawing)) {
      return;
    }
    dragState.value = { mode: 'object', drawingId: drawing.id, startAnchor: anchor };
  }

  function endDrag() {
    dragState.value = null;
  }

  function resolveDragCommit(
    drawing: KlineDrawing | null,
    anchor: KlineDrawingAnchor | null,
    candles: KlineCandle[],
  ): KlineDrawingDragCommit | null {
    const state = dragState.value;
    if (!state || !drawing || !anchor || drawing.locked || !isEditableDrawing(drawing)) {
      return null;
    }
    if (state.mode === 'anchor' && typeof state.anchorIndex === 'number') {
      return { type: 'anchor', drawingId: drawing.id, anchors: moveDrawingByAnchor(drawing, state.anchorIndex, anchor) };
    }
    const timeDelta = computeCandleIndexDelta(candles, state.startAnchor.time, anchor.time);
    const priceDelta = anchor.price - state.startAnchor.price;
    return { type: 'move', drawingId: drawing.id, anchors: moveDrawingByDelta(drawing, candles, timeDelta, priceDelta) };
  }

  return {
    dragState,
    beginAnchorDrag,
    beginBodyDrag,
    endDrag,
    resolveDragCommit,
  };
}
