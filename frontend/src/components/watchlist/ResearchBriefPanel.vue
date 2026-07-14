<script setup lang="ts">
import { computed } from 'vue';

import type { ResearchDriverCategory, WatchlistResearchBrief } from '../../types/api';
import { formatMarketTime } from '../../utils/time';

const props = defineProps<{
  researchBrief: WatchlistResearchBrief;
}>();

// 后端 WatchlistResearchBriefView.drivers 为可选字段(缺省即空列表),兜底为空数组。
const drivers = computed(() => props.researchBrief.drivers ?? []);

const groupedDrivers = computed(() => {
  const groups = new Map<ResearchDriverCategory, typeof drivers.value>();
  for (const driver of drivers.value) {
    const existing = groups.get(driver.category) ?? [];
    existing.push(driver);
    groups.set(driver.category, existing);
  }
  return Array.from(groups.entries());
});

function categoryLabel(category: ResearchDriverCategory) {
  return {
    policy_macro: '政策/监管/宏观',
    company_action: '产品/订单/公司动作',
    supply_chain: '产业链传导',
    price_action: '价格异动解释',
  }[category];
}

function actionLabel(level: WatchlistResearchBrief['top_action_level']) {
  return {
    act_now: '立即看',
    watch_today: '今日跟踪',
    know_only: '知道即可',
    none: '暂无驱动',
  }[level];
}
</script>

<template>
  <div class="ai-frame">
  <section
    class="ai-frame-inner grid gap-4 p-4"
    data-role="research-brief-panel"
  >
    <div class="flex flex-wrap items-start justify-between gap-3" data-role="research-brief-summary">
      <div class="grid gap-1">
        <p class="text-[11px] uppercase tracking-[0.24em] text-ai">✦ Research Brief</p>
        <strong class="text-text">近 {{ researchBrief.window_days }} 天驱动压缩</strong>
        <p class="text-sm text-text-soft">
          当前优先级：{{ actionLabel(researchBrief.top_action_level) }}
          <template v-if="researchBrief.has_unexplained_price_move"> · 存在价格异动待解释</template>
        </p>
      </div>
      <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">
        {{ drivers.length }} drivers · {{ formatMarketTime(researchBrief.generated_at, researchBrief.market) }}
      </span>
    </div>

    <div v-if="!drivers.length" class="rounded-md border border-border bg-panel-stronger px-4 py-3 text-sm text-text-soft" data-role="research-brief-empty">
      暂无可归因驱动，继续关注价格和原始新闻流。
    </div>

    <div v-else class="grid gap-3">
      <section
        v-for="[category, drivers] in groupedDrivers"
        :key="category"
        class="grid gap-2 rounded-md border border-border bg-panel-stronger p-3"
        :data-role="`research-driver-group-${category}`"
      >
        <div class="flex items-center justify-between gap-2">
          <strong class="text-sm text-text">{{ categoryLabel(category) }}</strong>
          <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ drivers.length }} items</span>
        </div>
        <article
          v-for="driver in drivers"
          :key="driver.news_item.id"
          class="grid gap-1.5 rounded-md border border-border bg-panel-strong p-3"
          :data-role="`research-driver-item-${driver.news_item.id}`"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <strong class="text-sm text-text">{{ driver.news_item.title }}</strong>
            <span class="text-[11px] uppercase tracking-[0.14em] text-accent">{{ actionLabel(driver.action_level) }}</span>
          </div>
          <p class="text-sm text-text-soft">{{ driver.reason }}</p>
          <div class="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.12em] text-text-faint">
            <span>{{ driver.news_item.source_name }}</span>
            <span>{{ formatMarketTime(driver.news_item.published_at ?? driver.news_item.fetched_at, driver.news_item.market) }}</span>
          </div>
        </article>
      </section>
    </div>
  </section>
  </div>
</template>
