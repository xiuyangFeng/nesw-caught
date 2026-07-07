<script setup lang="ts">
import { computed, ref } from 'vue';

import type { TokenDailyStats } from './types';

const props = defineProps<{
  daily: TokenDailyStats[];
}>();

const hoveredIdx = ref<number | null>(null);
const dailyData = computed(() => props.daily || []);

const chartWidth = 500;
const chartHeight = 140;
const paddingLeft = 40;
const paddingRight = 20;
const paddingTop = 15;
const paddingBottom = 20;

function handleChartMouseMove(e: MouseEvent) {
  if (!dailyData.value.length) return;
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const relativeX = clickX / rect.width;
  const idx = Math.round(relativeX * (dailyData.value.length - 1));
  if (idx >= 0 && idx < dailyData.value.length) {
    hoveredIdx.value = idx;
  }
}

function handleChartMouseLeave() {
  hoveredIdx.value = null;
}

const chartPoints = computed(() => {
  const data = dailyData.value;
  if (!data.length) return [];
  const maxVal = Math.max(...data.map(d => d.total_tokens), 0) || 1000;
  const W = chartWidth - paddingLeft - paddingRight;
  const H = chartHeight - paddingTop - paddingBottom;

  return data.map((d, i) => {
    const x = paddingLeft + (data.length > 1 ? (i / (data.length - 1)) * W : W / 2);
    const y = chartHeight - paddingBottom - (d.total_tokens / maxVal) * H;
    return { x, y, ...d };
  });
});

const linePath = computed(() => {
  const pts = chartPoints.value;
  if (!pts.length) return '';
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
});

const areaPath = computed(() => {
  const pts = chartPoints.value;
  if (!pts.length) return '';
  const start = linePath.value;
  const lastX = pts[pts.length - 1].x;
  const firstX = pts[0].x;
  const yBottom = chartHeight - paddingBottom;
  return `${start} L ${lastX.toFixed(1)} ${yBottom} L ${firstX.toFixed(1)} ${yBottom} Z`;
});
</script>

<template>
  <div class="mt-5 relative border border-border/50 bg-white/[0.01] rounded-2xl p-4 overflow-hidden" data-role="token-trend-card">
    <div class="flex items-center justify-between mb-3">
      <div class="text-xs font-bold text-text-faint tracking-wider uppercase font-mono">7日 Token 消耗趋势</div>
      <div class="text-[10px] text-muted font-mono">鼠标悬停可显示明细</div>
    </div>

    <div v-if="dailyData.length > 0" class="relative w-full h-[140px]" data-role="chart-container">
      <svg
        class="w-full h-full cursor-crosshair overflow-visible"
        viewBox="0 0 500 140"
        preserveAspectRatio="none"
        @mousemove="handleChartMouseMove"
        @mouseleave="handleChartMouseLeave"
      >
        <defs>
          <linearGradient id="chartAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.25" />
            <stop offset="100%" stop-color="#22d3ee" stop-opacity="0.0" />
          </linearGradient>
        </defs>

        <!-- Horizontal grid lines -->
        <g stroke="rgba(255,255,255,0.04)" stroke-dasharray="2 3">
          <line x1="40" y1="15" x2="480" y2="15" />
          <line x1="40" y1="50" x2="480" y2="50" />
          <line x1="40" y1="85" x2="480" y2="85" />
          <line x1="40" y1="120" x2="480" y2="120" />
        </g>

        <!-- X Axis Labels -->
        <g fill="rgba(255,255,255,0.4)" font-size="8" font-family="monospace" text-anchor="middle">
          <text v-for="(p, i) in chartPoints" :key="i" :x="p.x" y="134">
            {{ p.date && typeof p.date === 'string' ? p.date.substring(5) : (p.date || '--') }}
          </text>
        </g>

        <!-- Y Axis indicators (Max / Min) -->
        <g fill="rgba(255,255,255,0.25)" font-size="7" font-family="monospace" text-anchor="end">
          <text x="32" y="18">{{ Math.max(...dailyData.map(d => d.total_tokens), 0).toLocaleString() }}</text>
          <text x="32" y="123">0</text>
        </g>

        <!-- Area block -->
        <path :d="areaPath" fill="url(#chartAreaGrad)" />

        <!-- Highlight line -->
        <path :d="linePath" fill="none" stroke="#22d3ee" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />

        <!-- Cursor crosshair vertical line -->
        <line
          v-if="hoveredIdx !== null && chartPoints[hoveredIdx]"
          :x1="chartPoints[hoveredIdx].x"
          y1="15"
          :x2="chartPoints[hoveredIdx].x"
          y2="120"
          stroke="#22d3ee"
          stroke-opacity="0.3"
          stroke-dasharray="2 2"
        />

        <!-- Dots -->
        <circle
          v-for="(p, i) in chartPoints"
          :key="i"
          :cx="p.x"
          :cy="p.y"
          r="3.5"
          fill="#0f172a"
          :stroke="hoveredIdx === i ? '#ffffff' : '#22d3ee'"
          stroke-width="1.5"
          :style="{ transform: hoveredIdx === i ? 'scale(1.5)' : 'none' }"
          class="transition-all duration-100 origin-center"
        />
      </svg>

      <!-- Interactive HTML tooltip popover -->
      <div
        v-if="hoveredIdx !== null && chartPoints[hoveredIdx]"
        class="absolute pointer-events-none rounded-xl border border-cyan-500/30 bg-black/90 p-2.5 text-[10px] text-text-faint font-mono shadow-lg shadow-cyan-950/20 backdrop-blur-md z-10 space-y-1 w-28"
        :style="{
          left: `${(chartPoints[hoveredIdx].x / chartWidth) * 100}%`,
          top: `${(chartPoints[hoveredIdx].y / chartHeight) * 100 - 50}%`,
          transform: 'translate(-50%, -100%)'
        }"
      >
        <div class="text-text font-bold border-b border-white/10 pb-0.5 mb-1">{{ chartPoints[hoveredIdx].date }}</div>
        <div class="flex justify-between gap-1">
          <span>Total:</span>
          <span class="text-cyan-400 font-bold">{{ chartPoints[hoveredIdx].total_tokens.toLocaleString() }}</span>
        </div>
        <div class="flex justify-between gap-1 text-[9px] text-muted">
          <span>Prompt:</span>
          <span>{{ chartPoints[hoveredIdx].prompt_tokens.toLocaleString() }}</span>
        </div>
        <div class="flex justify-between gap-1 text-[9px] text-muted">
          <span>Reply:</span>
          <span>{{ chartPoints[hoveredIdx].completion_tokens.toLocaleString() }}</span>
        </div>
      </div>
    </div>

    <div v-else class="flex flex-col items-center justify-center py-8 text-center border border-dashed border-border/40 rounded-xl bg-white/[0.005]">
      <span class="text-xl mb-1">📊</span>
      <p class="text-xs text-text-faint">暂无足够历史 Token 用量趋势数据</p>
    </div>
  </div>
</template>
