<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { useMarketOverviewStore } from '../../stores/marketOverviewStore';
import { formatNumber, formatPercent } from '../../utils/format';

const store = useMarketOverviewStore();

interface TickerItem {
  key: string;
  marketName: string;
  name: string;
  price: number | null;
  changePercent: number | null;
  available: boolean;
}

// ^VIX 只参与美股情绪计算,不在行情条展示(与 MarketOverviewCard 约定一致)。
const items = computed<TickerItem[]>(() => {
  const markets = store.overview?.markets ?? [];
  return markets.flatMap((market) =>
    market.indices
      .filter((index) => index.symbol !== '^VIX')
      .map((index) => ({
        key: `${market.market}:${index.symbol}`,
        marketName: market.display_name,
        name: index.display_name,
        price: index.price ?? null,
        changePercent: index.change_percent ?? null,
        available: index.status === 'ok' && index.price != null,
      })),
  );
});

// 无缝滚动:列表渲染两份,动画平移 -50% 即可循环;时长随条目数伸缩。
const marqueeDuration = computed(() => `${Math.max(20, items.value.length * 3)}s`);

// 涨跌幅变化时的闪烁提示:key -> 'up' | 'down',600ms 后自动清除。
const flashes = ref<Record<string, 'up' | 'down'>>({});
const flashTimers = new Map<string, ReturnType<typeof setTimeout>>();

watch(
  items,
  (next, prev) => {
    const prevByKey = new Map(prev.map((item) => [item.key, item.changePercent]));
    for (const item of next) {
      const before = prevByKey.get(item.key);
      if (before === undefined || before === null || item.changePercent === null || item.changePercent === before) {
        continue;
      }
      flashes.value[item.key] = item.changePercent > before ? 'up' : 'down';
      const existing = flashTimers.get(item.key);
      if (existing) {
        clearTimeout(existing);
      }
      flashTimers.set(
        item.key,
        setTimeout(() => {
          delete flashes.value[item.key];
          flashTimers.delete(item.key);
        }, 600),
      );
    }
  },
);

onBeforeUnmount(() => {
  for (const timer of flashTimers.values()) {
    clearTimeout(timer);
  }
  flashTimers.clear();
});

function changeToneClass(value: number | null) {
  if ((value ?? 0) > 0) {
    return 'text-positive';
  }
  if ((value ?? 0) < 0) {
    return 'text-negative';
  }
  return 'text-text-soft';
}
</script>

<template>
  <div
    v-if="items.length > 0"
    class="surface group overflow-hidden rounded-md border border-border"
    data-role="market-ticker-strip"
  >
    <div
      class="flex w-max items-center gap-6 px-4 py-2 ticker-marquee group-hover:[animation-play-state:paused]"
      :style="{ animationDuration: marqueeDuration }"
    >
      <div
        v-for="(item, copyIndex) in [...items, ...items]"
        :key="`${item.key}-${copyIndex}`"
        class="flex shrink-0 items-baseline gap-1.5 font-mono text-[12px] tabular-nums rounded px-1 transition-colors duration-500"
        :class="{
          'bg-[var(--positive-soft)]': flashes[item.key] === 'up',
          'bg-[var(--negative-soft)]': flashes[item.key] === 'down',
        }"
        :data-role="`ticker-item-${item.key}`"
      >
        <span class="text-[10px] uppercase tracking-wider text-text-faint">{{ item.marketName }}</span>
        <span class="text-text-soft">{{ item.name }}</span>
        <template v-if="item.available">
          <span class="font-semibold text-text" data-role="ticker-price">{{ formatNumber(item.price) }}</span>
          <span class="font-semibold" :class="changeToneClass(item.changePercent)" data-role="ticker-change">
            {{ formatPercent(item.changePercent) }}
          </span>
        </template>
        <span v-else class="text-text-faint" data-role="ticker-unavailable">--</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ticker-marquee {
  animation-name: ticker-scroll;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

@keyframes ticker-scroll {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
}
</style>
