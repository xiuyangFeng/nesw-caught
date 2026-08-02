<script setup lang="ts">
import { computed } from 'vue';

import type { QuantSentimentLabel } from '../../types/api';

const props = defineProps<{
  // 后端量化情绪分,区间 [-1, 1];null 表示数据不足。
  score: number | null;
  label: QuantSentimentLabel;
}>();

// score [-1, 1] 映射到 [0, 1] 作为仪表进度;null 时指针回落到中位并置灰。
const ratio = computed(() => {
  if (props.score === null) {
    return 0.5;
  }
  return Math.min(1, Math.max(0, (props.score + 1) / 2));
});

const pointerAngle = computed(() => ratio.value * 180);

const displayValue = computed(() => (props.score === null ? '--' : String(Math.round(ratio.value * 100))));

const LABEL_TEXT: Record<QuantSentimentLabel, string> = {
  panic: '极度恐慌',
  fear: '恐慌',
  neutral: '中性',
  greed: '贪婪',
  greed_extreme: '极度贪婪',
  unknown: '数据不足',
};

const labelText = computed(() => LABEL_TEXT[props.label] ?? LABEL_TEXT.unknown);

// 标签着色与 MarketOverviewCard 的五色体系保持一致:
// panic 红 / fear 橙 / neutral 灰 / greed 浅绿 / greed_extreme 深绿(主题 --negative 为绿)。
const LABEL_CLASS: Record<QuantSentimentLabel, string> = {
  panic: 'text-danger',
  fear: 'text-warning',
  neutral: 'text-text-faint',
  greed: 'text-[var(--negative)]',
  greed_extreme: 'text-[var(--negative)]',
  unknown: 'text-text-faint',
};

const labelClass = computed(() => LABEL_CLASS[props.label] ?? LABEL_CLASS.unknown);

// 半圆弧长:半径 80 的半圆 ≈ 251.33,五等分表示 恐慌/偏慌/中性/贪婪/极贪 五个区间。
const ZONE_LENGTH = 251.33 / 5;
const zones = [
  { color: 'var(--danger)', offset: 0 },
  { color: 'var(--warning)', offset: -ZONE_LENGTH },
  { color: 'color-mix(in srgb, var(--text) 25%, transparent)', offset: -ZONE_LENGTH * 2 },
  { color: 'color-mix(in srgb, var(--negative) 55%, transparent)', offset: -ZONE_LENGTH * 3 },
  { color: 'var(--negative)', offset: -ZONE_LENGTH * 4 },
];
</script>

<template>
  <div class="relative w-full max-w-[180px] aspect-[2/1.1] mx-auto" data-role="fear-greed-gauge">
    <svg viewBox="0 0 200 110" class="w-full h-auto overflow-visible">
      <!-- 弧形底色 -->
      <path
        d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none"
        stroke="color-mix(in srgb, var(--text) 6%, transparent)"
        stroke-width="12"
        stroke-linecap="round"
      />

      <!-- 五段情绪区间色带 -->
      <path
        v-for="zone in zones"
        :key="zone.offset"
        d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none"
        :stroke="zone.color"
        stroke-width="12"
        :stroke-dasharray="`${ZONE_LENGTH - 2} 9999`"
        :stroke-dashoffset="zone.offset"
        opacity="0.85"
      />

      <!-- 内围刻度圈 -->
      <path
        d="M 32 100 A 68 68 0 0 1 168 100"
        fill="none"
        stroke="color-mix(in srgb, var(--text) 5%, transparent)"
        stroke-width="1"
      />

      <!-- 中心枢轴 -->
      <circle cx="100" cy="100" r="12" fill="var(--panel)" fill-opacity="0.9" stroke="color-mix(in srgb, var(--text) 15%, transparent)" stroke-width="1" />
      <circle cx="100" cy="100" r="5" fill="var(--text)" />

      <!-- 指针(数据刷新时平滑摆动) -->
      <g
        :style="{
          transform: `rotate(${pointerAngle - 90}deg)`,
          transformOrigin: '100px 100px',
          transition: 'transform 1.2s cubic-bezier(0.16, 1, 0.3, 1)',
          opacity: score === null ? 0.35 : 1,
        }"
        data-role="fear-greed-pointer"
      >
        <line x1="100" y1="100" x2="100" y2="36" stroke="var(--text)" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="100" cy="34" r="3" fill="var(--accent)" />
      </g>
    </svg>

    <!-- 数值与标签叠加 -->
    <div class="absolute inset-x-0 bottom-0 flex flex-col items-center">
      <span class="text-[22px] font-bold leading-none text-text font-mono tabular-nums" data-role="fear-greed-value">
        {{ displayValue }}
      </span>
      <span class="mt-1 text-[11px] font-semibold tracking-wider" :class="labelClass" data-role="fear-greed-label">
        {{ labelText }}
      </span>
    </div>
  </div>
</template>
