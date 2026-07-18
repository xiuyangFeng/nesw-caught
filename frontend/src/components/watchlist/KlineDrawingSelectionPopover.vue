<script setup lang="ts">
import type { KlineDrawing, KlineDrawingStyle } from '../../types/api';
import { readCssVar } from '../../utils/cssVars';

// 色板按钮：emit 出去的色值会持久化并喂给 SVG/canvas 渲染，故用 helper 取令牌具体值。
const warmColor = readCssVar('--warning', '#ffb66d');
const coolColor = readCssVar('--system', '#7dd3fc');

defineProps<{
  drawing: KlineDrawing | null;
  selectedDrawings?: KlineDrawing[];
}>();

const emit = defineEmits<{
  styleChange: [style: Partial<KlineDrawingStyle>];
  drawingLockToggle: [];
  drawingVisibleToggle: [];
  drawingDuplicate: [];
  drawingDelete: [];
  drawingGroupLockToggle: [];
  drawingGroupVisibleToggle: [];
  drawingGroupDuplicate: [];
  drawingGroupDelete: [];
}>();
</script>

<template>
  <div
    v-if="drawing || (selectedDrawings?.length ?? 0) > 1"
    class="absolute right-3 top-3 z-20 flex flex-wrap items-center gap-2 rounded-[14px] border border-border/70 bg-panel-stronger/90 px-3 py-2"
    data-role="drawing-selection-popover"
  >
    <template v-if="drawing">
      <button type="button" data-role="drawing-color-warm" class="h-6 w-6 rounded-full" :style="{ backgroundColor: warmColor }" @click="emit('styleChange', { color: warmColor })" />
      <button type="button" data-role="drawing-color-cool" class="h-6 w-6 rounded-full" :style="{ backgroundColor: coolColor }" @click="emit('styleChange', { color: coolColor })" />
      <button type="button" data-role="drawing-line-solid" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('styleChange', { lineStyle: 'solid' })">实线</button>
      <button type="button" data-role="drawing-line-dashed" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('styleChange', { lineStyle: 'dashed' })">虚线</button>
      <button type="button" data-role="drawing-width-thin" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('styleChange', { lineWidth: 1 })">细</button>
      <button type="button" data-role="drawing-width-thick" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('styleChange', { lineWidth: 3 })">粗</button>
      <button type="button" data-role="drawing-lock-toggle" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingLockToggle')">
        {{ drawing.locked ? '解锁' : '锁定' }}
      </button>
      <button type="button" data-role="drawing-visible-toggle" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingVisibleToggle')">
        {{ drawing.visible ? '隐藏' : '显示' }}
      </button>
      <button type="button" data-role="drawing-duplicate" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingDuplicate')">复制</button>
      <button type="button" data-role="drawing-delete" class="rounded-full border border-danger/40 px-2 py-1 text-[11px] text-danger" @click="emit('drawingDelete')">删除</button>
    </template>
    <template v-else>
      <span data-role="drawing-group-count" class="text-[11px] uppercase tracking-[0.14em] text-text-faint">已选 {{ selectedDrawings?.length ?? 0 }} 个对象</span>
      <button type="button" data-role="drawing-group-lock-toggle" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingGroupLockToggle')">批量锁定</button>
      <button type="button" data-role="drawing-group-visible-toggle" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingGroupVisibleToggle')">批量显隐</button>
      <button type="button" data-role="drawing-group-duplicate" class="rounded-full border border-border/70 px-2 py-1 text-[11px] text-text-faint" @click="emit('drawingGroupDuplicate')">批量复制</button>
      <button type="button" data-role="drawing-group-delete" class="rounded-full border border-danger/40 px-2 py-1 text-[11px] text-danger" @click="emit('drawingGroupDelete')">批量删除</button>
    </template>
  </div>
</template>
