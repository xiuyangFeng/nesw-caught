<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    positiveTrend: number[];
    negativeTrend: number[];
    width?: number;
    height?: number;
  }>(),
  {
    width: 320,
    height: 120,
  }
);

// 确保趋势数组长度为 24 且数值有效
const positiveData = computed(() => {
  const data = [...props.positiveTrend];
  while (data.length < 24) data.unshift(0);
  return data.slice(-24);
});

const negativeData = computed(() => {
  const data = [...props.negativeTrend];
  while (data.length < 24) data.unshift(0);
  return data.slice(-24);
});

// 计算所有趋势中的最大值，用于 y 轴缩放
const maxValue = computed(() => {
  const maxVal = Math.max(...positiveData.value, ...negativeData.value);
  return maxVal > 0 ? maxVal : 1;
});

// 布局常量
const paddingX = 8;
const paddingY = 16;
const chartWidth = computed(() => props.width - paddingX * 2);
const chartHeight = computed(() => props.height - paddingY * 2);

// 计算 24 个点的坐标
function getPoints(data: number[]) {
  const stepX = chartWidth.value / 23;
  return data.map((val, index) => {
    const ratio = val / maxValue.value;
    const x = paddingX + index * stepX;
    const y = paddingY + chartHeight.value - ratio * chartHeight.value;
    return { x, y };
  });
}

const positivePoints = computed(() => getPoints(positiveData.value));
const negativePoints = computed(() => getPoints(negativeData.value));

// 转换为 polyline points 属性格式
const positiveLineString = computed(() =>
  positivePoints.value.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
);

const negativeLineString = computed(() =>
  negativePoints.value.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
);

// 面积图闭合路径（延伸到底部）
const positiveAreaString = computed(() => {
  const points = positivePoints.value;
  if (points.length === 0) return '';
  const first = points[0];
  const last = points[points.length - 1];
  const bottomY = paddingY + chartHeight.value;
  return `${first.x.toFixed(1)},${bottomY} ${positiveLineString.value} ${last.x.toFixed(1)},${bottomY}`;
});

const negativeAreaString = computed(() => {
  const points = negativePoints.value;
  if (points.length === 0) return '';
  const first = points[0];
  const last = points[points.length - 1];
  const bottomY = paddingY + chartHeight.value;
  return `${first.x.toFixed(1)},${bottomY} ${negativeLineString.value} ${last.x.toFixed(1)},${bottomY}`;
});

// 虚线网格坐标计算
const gridLines = computed(() => {
  const h = chartHeight.value;
  const bottom = paddingY + h;
  return [
    bottom - h * 0.33,
    bottom - h * 0.66,
    bottom - h,
  ];
});
</script>

<template>
  <article
    class="surface rounded-[14px] border border-border/90 bg-[linear-gradient(180deg,rgba(11,18,28,0.98),rgba(8,14,23,0.98))] p-[16px] flex flex-col justify-between"
    data-role="sentiment-trend-card"
  >
    <div class="w-full flex items-center justify-between mb-1">
      <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted">24小時輿情波動趨勢</p>
      <div class="flex items-center gap-3 text-[10px]">
        <span class="flex items-center gap-1 text-positive">
          <span class="w-2 h-0.5 bg-positive rounded"></span>
          利好走势
        </span>
        <span class="flex items-center gap-1 text-negative">
          <span class="w-2 h-0.5 bg-negative rounded"></span>
          利空走势
        </span>
      </div>
    </div>

    <!-- SVG Trend Area -->
    <div class="relative w-full flex-grow mt-2">
      <svg
        :viewBox="`0 0 ${width} ${height}`"
        class="w-full h-auto overflow-visible"
        fill="none"
        aria-hidden="true"
        data-role="trend-svg"
      >
        <defs>
          <!-- 利好渐变 -->
          <linearGradient id="posAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--positive)" stop-opacity="0.22" />
            <stop offset="100%" stop-color="var(--positive)" stop-opacity="0.0" />
          </linearGradient>
          <!-- 利空渐变 -->
          <linearGradient id="negAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--negative)" stop-opacity="0.22" />
            <stop offset="100%" stop-color="var(--negative)" stop-opacity="0.0" />
          </linearGradient>
        </defs>

        <!-- 横向虚线网格 -->
        <line
          v-for="(y, index) in gridLines"
          :key="index"
          :x1="paddingX"
          :y1="y"
          :x2="width - paddingX"
          :y2="y"
          stroke="rgba(255,255,255,0.04)"
          stroke-width="1"
          stroke-dasharray="3,3"
        />

        <!-- 利好填充面积与折线 -->
        <polygon :points="positiveAreaString" fill="url(#posAreaGrad)" />
        <polyline
          :points="positiveLineString"
          stroke="var(--positive)"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          :style="{ transition: 'points 0.5s ease' }"
        />

        <!-- 利空填充面积与折线 -->
        <polygon :points="negativeAreaString" fill="url(#negAreaGrad)" />
        <polyline
          :points="negativeLineString"
          stroke="var(--negative)"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          :style="{ transition: 'points 0.5s ease' }"
        />

        <!-- X轴刻度文字 (24小时分段) -->
        <g class="text-[9px] fill-muted/70 text-anchor-middle font-mono">
          <text :x="paddingX" :y="height" text-anchor="start">24h前</text>
          <text :x="paddingX + chartWidth * 0.25" :y="height" text-anchor="middle">18h前</text>
          <text :x="paddingX + chartWidth * 0.5" :y="height" text-anchor="middle">12h前</text>
          <text :x="paddingX + chartWidth * 0.75" :y="height" text-anchor="middle">6h前</text>
          <text :x="width - paddingX" :y="height" text-anchor="end">現在</text>
        </g>
      </svg>
    </div>
  </article>
</template>
