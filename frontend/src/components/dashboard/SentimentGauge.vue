<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  positiveCount: number;
  negativeCount: number;
}>();

const total = computed(() => props.positiveCount + props.negativeCount);

const positiveRatio = computed(() => {
  if (total.value === 0) {
    return 0.5; // 默认为中性 (50%)
  }
  return props.positiveCount / total.value;
});

// 计算旋转角度 (0% = 0度, 100% = 180度)
const pointerAngle = computed(() => {
  return positiveRatio.value * 180;
});

const sentimentText = computed(() => {
  if (total.value === 0) {
    return '无足够新闻';
  }
  const ratio = positiveRatio.value;
  if (ratio > 0.75) {
    return '极度乐观 (Strong Bullish)';
  }
  if (ratio > 0.55) {
    return '乐观主导 (Bullish)';
  }
  if (ratio > 0.45) {
    return '中性平稳 (Neutral)';
  }
  if (ratio > 0.25) {
    return '悲观偏空 (Bearish)';
  }
  return '恐慌弥漫 (Strong Bearish)';
});

const sentimentDesc = computed(() => {
  if (total.value === 0) {
    return '等待抓取新闻数据生成舆情画像';
  }
  const ratio = positiveRatio.value;
  if (ratio > 0.75) {
    return '政策红利或公司利好密集释放，市场情绪高涨。';
  }
  if (ratio > 0.55) {
    return '偏正面消息占据主动，可关注相关个股催化。';
  }
  if (ratio > 0.45) {
    return '多空力量相对均衡，建议耐心观察核心异动股。';
  }
  if (ratio > 0.25) {
    return '市场承受抛压与行业利空警告，注意潜在下行风险。';
  }
  return '负面舆情或黑天鹅事件发酵，风险预警度极高。';
});

const displayPercentage = computed(() => {
  return Math.round(positiveRatio.value * 100);
});
</script>

<template>
  <article
    class="surface rounded-md border border-border p-4 flex flex-col items-center justify-between"
    data-role="sentiment-gauge-card"
  >
    <div class="w-full flex items-center justify-between mb-2">
      <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted">輿情偏好羅盤</p>
      <span class="text-[10px] bg-white/[0.04] border border-border px-2 py-0.5 rounded-full text-muted font-mono tabular-nums">
        利好 {{ positiveCount }} / 利空 {{ negativeCount }}
      </span>
    </div>

    <!-- SVG Gauge Area -->
    <div class="relative w-full max-w-[220px] aspect-[2/1.1] flex items-center justify-center mt-2">
      <svg viewBox="0 0 200 110" class="w-full h-auto overflow-visible">
        <!-- 渐变色与滤镜定义 -->
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <!-- 极左利空(绿) -> 中性(琥珀) -> 极右利好(红) -->
            <stop offset="0%" stop-color="var(--negative)" />
            <stop offset="50%" stop-color="var(--warning)" />
            <stop offset="100%" stop-color="var(--positive)" />
          </linearGradient>
          <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <!-- 精密辅助底轨 (外围刻度圈) -->
        <path
          d="M 6 100 A 94 94 0 0 1 194 100"
          fill="none"
          stroke="color-mix(in srgb, var(--text) 8%, transparent)"
          stroke-width="1.5"
          stroke-dasharray="2, 6"
        />

        <!-- 弧形底色 -->
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="color-mix(in srgb, var(--text) 6%, transparent)"
          stroke-width="12"
          stroke-linecap="round"
        />

        <!-- 弧形彩色渐变轨 -->
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="url(#gaugeGradient)"
          stroke-width="12"
          stroke-linecap="round"
          stroke-dasharray="251"
          stroke-dashoffset="0"
        />

        <!-- 内围精密刻度圈 -->
        <path
          d="M 32 100 A 68 68 0 0 1 168 100"
          fill="none"
          stroke="color-mix(in srgb, var(--text) 5%, transparent)"
          stroke-width="1"
        />

        <!-- 中心枢轴 -->
        <circle cx="100" cy="100" r="14" fill="var(--panel)" fill-opacity="0.9" stroke="color-mix(in srgb, var(--text) 15%, transparent)" stroke-width="1" />
        <circle cx="100" cy="100" r="6" fill="var(--text)" />

        <!-- 指针组合组 (带有旋转动效和尖端发光) -->
        <g
          :style="{
            transform: `rotate(${pointerAngle - 90}deg)`,
            transformOrigin: '100px 100px',
            transition: 'transform 1.4s cubic-bezier(0.16, 1, 0.3, 1)'
          }"
        >
          <!-- 指针线 -->
          <line
            x1="100"
            y1="100"
            x2="100"
            y2="34"
            stroke="var(--text)"
            stroke-width="2.5"
            stroke-linecap="round"
          />
          <!-- 尖端发光小点 -->
          <circle
            cx="100"
            cy="32"
            r="3.5"
            fill="var(--accent)"
            filter="url(#gaugeGlow)"
          />
        </g>
      </svg>

      <!-- 数值文字居中叠加 -->
      <div class="absolute bottom-1 flex flex-col items-center">
        <span class="text-[28px] font-bold tracking-tight leading-none text-text font-mono tabular-nums">
          {{ displayPercentage }}%
        </span>
        <span class="text-[10px] text-muted tracking-wider uppercase mt-1">利好占比</span>
      </div>
    </div>

    <!-- 情绪文本描述 -->
    <div class="w-full text-center mt-3 border-t border-border/40 pt-2.5">
      <strong class="block text-[13px] text-accent mb-0.5">{{ sentimentText }}</strong>
      <p class="m-0 text-[11px] text-muted leading-relaxed line-clamp-1">
        {{ sentimentDesc }}
      </p>
    </div>
  </article>
</template>
