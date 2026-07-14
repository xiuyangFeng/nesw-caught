<script setup lang="ts">
import type { WatchlistQuoteSummary } from '../../types/api';
import { formatNumber } from '../../utils/format';

defineProps<{
  quote: WatchlistQuoteSummary | null;
}>();
</script>

<template>
  <section class="grid gap-3 rounded-lg border border-border bg-panel p-4">
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
        class="rounded-md border border-border/70 bg-panel-strong p-3"
      >
        <span class="label-mono block">{{ label }}</span>
        <strong class="num text-text">{{ value }}</strong>
      </article>
    </div>
  </section>
</template>
