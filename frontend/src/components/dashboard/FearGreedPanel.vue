<script setup lang="ts">
import { computed } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { useMarketOverviewStore } from '../../stores/marketOverviewStore';
import type { MarketOverviewMarket, QuantSentimentLabel } from '../../types/api';
import { formatNumber } from '../../utils/format';
import FearGreedGauge from './FearGreedGauge.vue';

const store = useMarketOverviewStore();

const markets = computed(() => store.overview?.markets ?? []);
const initialLoading = computed(() => store.loading && markets.value.length === 0);

function quantLabel(market: MarketOverviewMarket): QuantSentimentLabel {
  const label = market.quant_sentiment?.label;
  if (label === 'panic' || label === 'fear' || label === 'neutral' || label === 'greed' || label === 'greed_extreme') {
    return label;
  }
  return 'unknown';
}

// 涨跌家数:汇总该市场板块条目的上涨/下跌/平盘家数,用于宽度条。
function breadthOf(market: MarketOverviewMarket) {
  if (market.boards.status !== 'ok') {
    return null;
  }
  let advance = 0;
  let decline = 0;
  let flat = 0;
  for (const item of market.boards.items) {
    advance += item.advance_count ?? 0;
    decline += item.decline_count ?? 0;
    flat += item.flat_count ?? 0;
  }
  const total = advance + decline + flat;
  if (total === 0) {
    return null;
  }
  return {
    advance,
    decline,
    flat,
    advancePct: (advance / total) * 100,
    flatPct: (flat / total) * 100,
    declinePct: (decline / total) * 100,
  };
}

function newsScoreOf(market: MarketOverviewMarket): number | null {
  const sentiment = market.news_sentiment;
  if (!sentiment || sentiment.status !== 'ok') {
    return null;
  }
  return sentiment.score ?? null;
}
</script>

<template>
  <SectionCard
    eyebrow="Fear & Greed Index"
    title="市场情绪与恐慌指数"
    subtitle="五大市场量化情绪:指数动量 + VIX + 涨跌家数合成,每 60 秒自动刷新"
    compact
    data-role="fear-greed-panel"
  >
    <p
      v-if="store.error"
      class="mb-2 rounded-[12px] border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
      data-role="fear-greed-error"
    >
      {{ store.error }}
    </p>

    <div v-if="initialLoading" class="py-6 text-center text-text-faint" data-role="fear-greed-loading">
      正在加载市场情绪…
    </div>

    <div v-else-if="markets.length > 0" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" data-role="fear-greed-grid">
      <article
        v-for="market in markets"
        :key="market.market"
        class="grid content-start gap-2.5 rounded-xl border border-border/80 bg-panel px-3.5 py-3"
        :data-role="`fear-greed-card-${market.market}`"
      >
        <header class="flex items-center justify-between gap-2">
          <strong class="truncate text-sm font-bold text-text">{{ market.display_name }}</strong>
          <span
            class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
            :class="market.is_open ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border bg-white/5 text-text-faint'"
            data-role="market-open-badge"
          >
            {{ market.is_open ? '开盘中' : '已闭市' }}
          </span>
        </header>

        <FearGreedGauge
          :score="market.quant_sentiment?.score ?? null"
          :label="quantLabel(market)"
        />

        <!-- 输入因子 -->
        <div class="grid grid-cols-3 gap-1 text-center" data-role="fear-greed-inputs">
          <div class="rounded-lg border border-border/60 px-1 py-1">
            <p class="m-0 text-[9px] uppercase tracking-wider text-text-faint">VIX</p>
            <p class="m-0 font-mono text-[12px] font-semibold tabular-nums text-text">
              {{ formatNumber(market.quant_sentiment?.inputs.vix, 1) }}
            </p>
          </div>
          <div class="rounded-lg border border-border/60 px-1 py-1">
            <p class="m-0 text-[9px] uppercase tracking-wider text-text-faint">涨跌比</p>
            <p class="m-0 font-mono text-[12px] font-semibold tabular-nums text-text">
              {{ market.quant_sentiment?.inputs.adv_ratio != null ? `${Math.round(market.quant_sentiment.inputs.adv_ratio * 100)}%` : '--' }}
            </p>
          </div>
          <div class="rounded-lg border border-border/60 px-1 py-1">
            <p class="m-0 text-[9px] uppercase tracking-wider text-text-faint">均涨跌</p>
            <p class="m-0 font-mono text-[12px] font-semibold tabular-nums text-text">
              {{ market.quant_sentiment?.inputs.avg_change_percent != null ? `${market.quant_sentiment.inputs.avg_change_percent.toFixed(2)}%` : '--' }}
            </p>
          </div>
        </div>

        <!-- 涨跌家数宽度条(红涨绿跌,随数据刷新平滑变化) -->
        <div v-if="breadthOf(market)" class="grid gap-1" data-role="breadth-bar">
          <div class="flex h-2 overflow-hidden rounded-full bg-white/5">
            <div
              class="h-full bg-[var(--positive)] transition-[width] duration-700"
              :style="{ width: `${breadthOf(market)!.advancePct}%` }"
              data-role="breadth-advance"
            />
            <div
              class="h-full bg-[color-mix(in_srgb,var(--text)_25%,transparent)] transition-[width] duration-700"
              :style="{ width: `${breadthOf(market)!.flatPct}%` }"
            />
            <div
              class="h-full bg-[var(--negative)] transition-[width] duration-700"
              :style="{ width: `${breadthOf(market)!.declinePct}%` }"
              data-role="breadth-decline"
            />
          </div>
          <div class="flex items-center justify-between font-mono text-[10px] tabular-nums">
            <span class="text-positive">涨 {{ breadthOf(market)!.advance }}</span>
            <span class="text-text-faint">平 {{ breadthOf(market)!.flat }}</span>
            <span class="text-negative">跌 {{ breadthOf(market)!.decline }}</span>
          </div>
        </div>
        <p v-else class="m-0 text-[11px] text-text-faint" data-role="breadth-empty">涨跌家数暂不可用</p>

        <!-- 新闻情绪分 -->
        <div class="flex items-center justify-between border-t border-border/60 pt-2 text-[11px]" data-role="news-sentiment-row">
          <span class="uppercase tracking-[0.14em] text-text-faint">新闻情绪</span>
          <span
            v-if="newsScoreOf(market) !== null"
            class="font-mono font-semibold tabular-nums"
            :class="(newsScoreOf(market) ?? 0) > 0 ? 'text-positive' : (newsScoreOf(market) ?? 0) < 0 ? 'text-negative' : 'text-text-soft'"
          >
            {{ newsScoreOf(market)!.toFixed(2) }}
          </span>
          <span v-else class="text-text-faint">样本不足</span>
        </div>
      </article>
    </div>

    <p v-else class="py-4 text-center text-text-faint" data-role="fear-greed-empty">暂无市场情绪数据</p>
  </SectionCard>
</template>
