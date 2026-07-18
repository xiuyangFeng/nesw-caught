<script setup lang="ts">
import { computed } from 'vue';

import Sparkline from '../common/Sparkline.vue';

const props = defineProps<{
  prices: number[];
}>();

// 涨跌染色：红涨绿跌，数据不足或持平时回落到主色单青。
// SVG 可直接消费 var(--xxx),无需 readCssVar,只映射 tone。
const tone = computed<'accent' | 'positive' | 'negative'>(() => {
  const prices = props.prices;
  if (prices.length < 2) {
    return 'accent';
  }
  const delta = prices[prices.length - 1] - prices[0];
  if (delta > 0) return 'positive';
  if (delta < 0) return 'negative';
  return 'accent';
});
</script>

<template>
  <div class="h-11 w-full" data-role="stock-sparkline">
    <Sparkline
      v-if="prices.length > 1"
      :values="prices"
      :width="160"
      :height="44"
      :tone="tone"
      preserveAspectRatio="none"
      class="h-full w-full"
    />
  </div>
</template>
