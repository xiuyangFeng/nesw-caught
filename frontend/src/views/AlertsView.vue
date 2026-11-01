<script setup lang="ts">
import { onMounted } from 'vue';
import { RouterLink } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { useAlertStore } from '../stores/alertStore';
import type { Alert } from '../types/api';
import { formatMarketTime } from '../utils/time';

const alertStore = useAlertStore();

const KIND_LABELS: Record<string, string> = {
  holding_price_move: '持仓异动',
  holding_news: '持仓新闻',
  watch_news_digest: '自选股新闻',
  sentiment_divergence: '情绪背离',
  overseas_major: '海外重大',
  sector_news_digest: '关注板块',
  opportunity_digest: '新机会',
};

const KIND_TONES: Record<string, string> = {
  holding_price_move: 'border-danger/40 bg-danger/10 text-danger',
  holding_news: 'border-accent/40 bg-accent/10 text-accent',
  watch_news_digest: 'border-border bg-panel-strong text-muted',
  sentiment_divergence: 'border-warning/40 bg-warning/10 text-warning',
  overseas_major: 'border-warning/40 bg-warning/10 text-warning',
  sector_news_digest: 'border-system/40 bg-system/10 text-system',
  opportunity_digest: 'border-ai/40 bg-ai/10 text-ai',
};

// 合并提醒条目；AI 模式下带 detail（如“利多·强 理由”），关键词兜底时没有。
type DigestItem = { news_id: number; symbol: string; name: string; title: string; detail?: string | null };

function kindLabel(alert: Alert) {
  return KIND_LABELS[alert.kind] ?? alert.kind;
}

function kindTone(alert: Alert) {
  return KIND_TONES[alert.kind] ?? 'border-border bg-panel-strong text-muted';
}

function alertTarget(alert: Alert): string | null {
  const newsId = alert.payload?.news_id;
  if (typeof newsId === 'number') {
    return `/news/${newsId}`;
  }
  if (alert.symbol) {
    return `/watchlist/${alert.symbol}`;
  }
  return null;
}

function digestItems(alert: Alert): DigestItem[] {
  const items = alert.payload?.items;
  return Array.isArray(items) ? (items as DigestItem[]) : [];
}

async function handleMarkRead(alert: Alert) {
  if (alert.read_at) {
    return;
  }
  try {
    await alertStore.markRead(alert.id);
  } catch {
    // 已读失败不影响浏览，下次刷新会同步
  }
}

async function handleMarkAllRead() {
  try {
    await alertStore.markAllRead();
  } catch {
    // 同上
  }
}

onMounted(() => {
  void alertStore.loadAlerts();
  void alertStore.refreshUnread();
});
</script>

<template>
  <div class="grid gap-4" data-role="alerts-view">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">提醒中心</h1>
        <p class="page-subtitle">
          持仓股全天涨跌超过 ±5% 立即提醒；AI 在线时由 AI 判断持仓新闻是否值得提醒（利多/利空且强度≥中），海外重大事件立即提醒，自选股、关注板块、新机会每 30 分钟合并一次；AI 不在线时回退关键词规则；22:00～08:00 不打扰，夜间提醒早上归入"隔夜汇总"。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-muted transition hover:text-text"
          data-role="alerts-refresh"
          @click="alertStore.loadAlerts()"
        >
          {{ alertStore.loading ? '刷新中…' : '刷新' }}
        </button>
        <button
          type="button"
          class="rounded-md border border-accent/40 px-3 py-1.5 text-sm text-accent transition hover:bg-accent/10"
          data-role="alerts-mark-all-read"
          @click="handleMarkAllRead"
        >
          全部已读
        </button>
      </div>
    </header>

    <p v-if="alertStore.error" class="rounded-[16px] border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
      {{ alertStore.error }}
    </p>

    <SectionCard
      v-if="!alertStore.loading && alertStore.alerts.length === 0"
      title="暂无提醒"
      subtitle="在自选股里填写持仓数量和成本后，持仓股的异动和新闻会出现在这里。"
      data-role="alerts-empty"
    />

    <template v-for="group in [
      { key: 'daytime', title: '近期提醒', eyebrow: 'Recent', items: alertStore.daytimeAlerts },
      { key: 'overnight', title: '隔夜汇总', eyebrow: 'Overnight', items: alertStore.overnightAlerts },
    ]" :key="group.key">
      <SectionCard
        v-if="group.items.length > 0"
        :title="group.title"
        :eyebrow="group.eyebrow"
        :data-role="`alerts-${group.key}`"
      >
        <ol class="grid gap-2">
          <li
            v-for="alert in group.items"
            :key="alert.id"
            class="grid gap-1.5 rounded-lg border px-3.5 py-3"
            :class="alert.read_at ? 'border-border/60 opacity-70' : 'border-border bg-panel-strong'"
            data-role="alert-item"
          >
            <div class="flex flex-wrap items-center gap-2 text-xs">
              <span
                v-if="!alert.read_at"
                class="h-2 w-2 rounded-full bg-accent"
                data-role="alert-unread-dot"
                aria-label="未读"
              />
              <span class="rounded-full border px-2 py-0.5" :class="kindTone(alert)">{{ kindLabel(alert) }}</span>
              <span class="font-mono text-text-faint">{{ formatMarketTime(alert.created_at, 'cn') }}</span>
              <button
                v-if="!alert.read_at"
                type="button"
                class="ml-auto text-text-faint transition hover:text-text"
                data-role="alert-mark-read"
                @click="handleMarkRead(alert)"
              >
                标记已读
              </button>
            </div>
            <RouterLink
              v-if="alertTarget(alert)"
              :to="alertTarget(alert)!"
              class="text-sm font-semibold text-text hover:text-accent"
              @click="handleMarkRead(alert)"
            >
              {{ alert.title }}
            </RouterLink>
            <p v-else class="m-0 text-sm font-semibold text-text">{{ alert.title }}</p>
            <ul v-if="digestItems(alert).length > 0" class="grid gap-1 text-sm text-muted">
              <li v-for="(item, index) in digestItems(alert)" :key="`${item.news_id}-${item.symbol}-${index}`" data-role="alert-digest-item">
                <RouterLink :to="`/news/${item.news_id}`" class="hover:text-accent" @click="handleMarkRead(alert)">
                  {{ item.name }}<span v-if="item.detail" class="text-text-faint" data-role="alert-digest-detail">（{{ item.detail }}）</span>：{{ item.title }}
                </RouterLink>
              </li>
            </ul>
            <p v-else-if="alert.body" class="m-0 whitespace-pre-line text-sm text-muted">{{ alert.body }}</p>
          </li>
        </ol>
      </SectionCard>
    </template>
  </div>
</template>
