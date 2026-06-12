<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    values: number[];
    width?: number;
    height?: number;
    tone?: 'accent' | 'positive' | 'negative';
  }>(),
  {
    width: 120,
    height: 28,
    tone: 'accent',
  },
);

const STROKE_BY_TONE: Record<'accent' | 'positive' | 'negative', string> = {
  accent: 'var(--accent)',
  positive: 'var(--positive)',
  negative: 'var(--negative)',
};

const strokeColor = computed(() => STROKE_BY_TONE[props.tone]);

const normalizedPoints = computed(() => {
  const values = props.values;
  if (values.length === 0) {
    return [] as Array<{ x: number; y: number }>;
  }
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min;
  const padding = 2;
  const innerHeight = props.height - padding * 2;
  const step = values.length > 1 ? (props.width - padding * 2) / (values.length - 1) : 0;

  return values.map((value, index) => {
    const ratio = range === 0 ? 0.5 : (value - min) / range;
    return {
      x: padding + index * step,
      y: padding + (1 - ratio) * innerHeight,
    };
  });
});

const linePoints = computed(() =>
  normalizedPoints.value.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' '),
);

const areaPoints = computed(() => {
  const points = normalizedPoints.value;
  if (points.length === 0) {
    return '';
  }
  const first = points[0];
  const last = points[points.length - 1];
  return `${first.x.toFixed(1)},${props.height} ${linePoints.value} ${last.x.toFixed(1)},${props.height}`;
});
</script>

<template>
  <svg
    v-if="values.length > 1"
    :width="width"
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    fill="none"
    aria-hidden="true"
    data-role="sparkline"
  >
    <polygon :points="areaPoints" :fill="strokeColor" opacity="0.12" />
    <polyline
      :points="linePoints"
      :stroke="strokeColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="none"
    />
  </svg>
</template>
