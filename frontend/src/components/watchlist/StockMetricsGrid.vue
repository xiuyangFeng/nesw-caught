<script setup lang="ts">
import type { WatchlistQuoteSummary } from '../../types/api';
import { formatNumber } from '../../utils/format';

defineProps<{
  quote: WatchlistQuoteSummary | null;
}>();
</script>

<template>
  <section class="grid gap-3 rounded-[22px] border border-border bg-[rgba(8,14,23,0.94)] p-4">
    <div class="grid gap-3 md:grid-cols-3">
      <article
        v-for="[label, value] in [
          ['Open', formatNumber(quote?.open_price)],
          ['High', formatNumber(quote?.day_high)],
          ['Low', formatNumber(quote?.day_low)],
          ['Prev Close', formatNumber(quote?.previous_close)],
          ['Volume', formatNumber(quote?.volume, 0)],
          ['Price', formatNumber(quote?.price)],
        ]"
        :key="label"
        class="rounded-[18px] border border-border/70 bg-black/10 p-3"
      >
        <span class="block text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ label }}</span>
        <strong class="text-text">{{ value }}</strong>
      </article>
    </div>
  </section>
</template>
