<script setup lang="ts">
import { computed } from 'vue';

// 回测净值曲线：纯前端自绘 SVG 折线 + 渐变面积（Terminal 风格，零依赖）。
// 数据点超过 500 时均匀降采样，保证 3 年日线级别的渲染量可控。

export interface EquityCurvePoint {
  date: string;
  equity: number;
}

const props = withDefaults(
  defineProps<{
    points?: EquityCurvePoint[];
    height?: number;
  }>(),
  { points: () => [], height: 180 },
);

const MAX_POINTS = 500;

const sampled = computed<EquityCurvePoint[]>(() => {
  const list = props.points ?? [];
  if (list.length <= MAX_POINTS) return list;
  const step = (list.length - 1) / (MAX_POINTS - 1);
  const result: EquityCurvePoint[] = [];
  for (let i = 0; i < MAX_POINTS; i += 1) {
    result.push(list[Math.round(i * step)]);
  }
  return result;
});

const width = 640;
const paddingX = 12;
const paddingY = 14;
const chartWidth = width - paddingX * 2;
const chartHeight = computed(() => props.height - paddingY * 2);

const bounds = computed(() => {
  const values = sampled.value.map((point) => point.equity);
  if (!values.length) return { min: 0, max: 1 };
  const min = Math.min(...values, 1);
  const max = Math.max(...values, 1);
  // 上下各留 8% 余量，曲线不贴边
  const span = max - min || 1;
  return { min: min - span * 0.08, max: max + span * 0.08 };
});

const coords = computed(() => {
  const list = sampled.value;
  if (list.length < 2) return [];
  const span = bounds.value.max - bounds.value.min || 1;
  const stepX = chartWidth / (list.length - 1);
  return list.map((point, index) => ({
    x: paddingX + index * stepX,
    y: paddingY + chartHeight.value - ((point.equity - bounds.value.min) / span) * chartHeight.value,
  }));
});

const polylinePoints = computed(() => coords.value.map((coord) => `${coord.x.toFixed(1)},${coord.y.toFixed(1)}`).join(' '));

const areaPath = computed(() => {
  if (coords.value.length < 2) return '';
  const first = coords.value[0];
  const last = coords.value[coords.value.length - 1];
  const baseline = paddingY + chartHeight.value;
  return `M ${first.x.toFixed(1)},${baseline.toFixed(1)} L ${polylinePoints.value.replace(/ /g, ' L ')} L ${last.x.toFixed(1)},${baseline.toFixed(1)} Z`;
});

const startLabel = computed(() => sampled.value[0]?.date ?? '');
const endLabel = computed(() => sampled.value[sampled.value.length - 1]?.date ?? '');
const finalEquity = computed(() => (sampled.value.length ? sampled.value[sampled.value.length - 1].equity : null));
const positive = computed(() => (finalEquity.value ?? 1) >= 1);
</script>

<template>
  <figure v-if="sampled.length >= 2" class="grid gap-1" data-role="equity-curve-chart">
    <figcaption class="flex items-center justify-between text-xs text-muted">
      <span>净值曲线（起点 = 1.0）</span>
      <span class="tabular-nums" :class="positive ? 'text-success' : 'text-danger'" data-role="equity-curve-final">
        期末 {{ (finalEquity ?? 1).toFixed(4) }}（{{ (((finalEquity ?? 1) - 1) * 100).toFixed(2) }}%）
      </span>
    </figcaption>
    <svg :viewBox="`0 0 ${width} ${height}`" class="w-full" role="img" aria-label="回测净值曲线" preserveAspectRatio="none">
      <defs>
        <linearGradient id="equity-curve-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="positive ? 'var(--accent)' : '#ef4444'" stop-opacity="0.35" />
          <stop offset="100%" stop-color="transparent" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <!-- 基准线：净值 = 1.0 -->
      <line
        v-if="bounds.min <= 1 && bounds.max >= 1"
        :x1="paddingX"
        :x2="width - paddingX"
        :y1="(paddingY + chartHeight - ((1 - bounds.min) / (bounds.max - bounds.min || 1)) * chartHeight).toFixed(1)"
        :y2="(paddingY + chartHeight - ((1 - bounds.min) / (bounds.max - bounds.min || 1)) * chartHeight).toFixed(1)"
        stroke="currentColor"
        class="text-border-strong"
        stroke-dasharray="4 4"
        stroke-width="1"
      />
      <path v-if="areaPath" :d="areaPath" fill="url(#equity-curve-fill)" data-role="equity-curve-area" />
      <polyline
        :points="polylinePoints"
        fill="none"
        :stroke="positive ? 'var(--accent)' : '#ef4444'"
        stroke-width="1.8"
        stroke-linejoin="round"
        stroke-linecap="round"
        data-role="equity-curve-line"
      />
    </svg>
    <div class="flex items-center justify-between text-[10px] text-muted">
      <span>{{ startLabel }}</span>
      <span>{{ endLabel }}</span>
    </div>
  </figure>
</template>
